"""Provider factory helpers for Graphiti service bootstrap."""

from __future__ import annotations

import json
import logging
import re
from contextlib import contextmanager
from typing import Any, get_args, get_origin

import graphiti_core.driver.falkordb_driver as falkordb_driver_module
import graphiti_core.graphiti as graphiti_module
import graphiti_core.utils.maintenance.edge_operations as edge_operations_module
import httpx
import openai
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.falkordb.operations.entity_edge_ops import FalkorEntityEdgeOperations
from graphiti_core.driver.falkordb.operations.entity_node_ops import FalkorEntityNodeOperations
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client import LLMConfig
from graphiti_core.llm_client.config import ModelSize
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.prompts.models import Message
from graphiti_core.search.search import SearchResults
from graphiti_core.utils import bulk_utils as bulk_utils_module
from openai import AsyncOpenAI
from pydantic import BaseModel

from miromem.graph_service.core.config import GraphServiceSettings

logger = logging.getLogger(__name__)

COMPAT_LLM_MAX_TOKENS = 2048
COMPAT_LLM_TEMPERATURE = 0.0
COMPAT_LLM_TIMEOUT_SECONDS = 180.0
COMPAT_EMBEDDING_TIMEOUT_SECONDS = 60.0
EDGE_RESOLUTION_MAX_CONCURRENCY = 2


def _clean_base_url(value: str) -> str | None:
    """Normalize blank OpenAI-compatible base URLs to None."""
    cleaned = value.strip()
    return cleaned or None


_FALKOR_PATCHED = False
_GRAPHITI_EDGE_RUNTIME_PATCHED = False


class StructuredOutputCompatClient(OpenAIGenericClient):
    """OpenAI-compatible client with provider-side JSON wording and shape normalization."""

    JSON_HINT = (
        "\n\nReturn valid JSON. The response must be a JSON object that matches the requested schema exactly."
    )

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 16384,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, Any]:
        normalized_messages = self._with_json_hint(messages) if response_model is not None else messages
        openai_messages: list[dict[str, str]] = []
        for message in normalized_messages:
            message.content = self._clean_input(message.content)
            if message.role in {"user", "system"}:
                openai_messages.append({"role": message.role, "content": message.content})

        response = await self.client.chat.completions.create(
            model=self.model or self.config.model,
            messages=openai_messages,
            temperature=self.temperature,
            max_tokens=max_tokens,
            response_format=self._build_response_format(response_model),
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        if response_model is None:
            return payload
        return self._normalize_payload_shape(payload, response_model, normalized_messages)

    def _build_response_format(self, response_model: type[BaseModel] | None) -> dict[str, Any]:
        if response_model is None:
            return {"type": "json_object"}
        if self._uses_compat_structured_output_mode():
            return {"type": "json_object"}

        schema_name = getattr(response_model, "__name__", "structured_response")
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": response_model.model_json_schema(),
            },
        }

    def _uses_compat_structured_output_mode(self) -> bool:
        base_url = (self.config.base_url or "").lower()
        return bool(base_url) and "api.openai.com" not in base_url

    def _with_json_hint(self, messages: list[Message]) -> list[Message]:
        cloned = [message.model_copy(deep=True) for message in messages]
        if cloned and cloned[0].role == "system":
            if "json" not in cloned[0].content.lower():
                cloned[0].content += self.JSON_HINT
            return cloned
        return [Message(role="system", content=self.JSON_HINT.strip()), *cloned]

    def _normalize_payload_shape(
        self,
        payload: dict[str, Any],
        response_model: type[BaseModel],
        messages: list[Message],
    ) -> dict[str, Any]:
        model_fields = response_model.model_fields
        if len(model_fields) != 1:
            return payload

        field_name, field_info = next(iter(model_fields.items()))
        if field_name in payload:
            normalized = dict(payload)
            normalized[field_name] = self._normalize_field_value(
                payload[field_name],
                field_info.annotation,
                messages,
            )
            return normalized

        if isinstance(payload, list):
            return {field_name: self._normalize_field_value(payload, field_info.annotation, messages)}

        alias_candidates = [
            field_name,
            field_name.replace("_", ""),
            _to_camel_case(field_name),
        ]
        if field_name.startswith("extracted_"):
            suffix = field_name[len("extracted_") :]
            alias_candidates.extend([suffix, _to_camel_case(suffix)])
        alias_candidates.extend(["items", "results", "data", "entities", "edges", "summaries"])

        for candidate in alias_candidates:
            value = payload.get(candidate)
            if value is not None:
                return {
                    field_name: self._normalize_field_value(
                        value,
                        field_info.annotation,
                        messages,
                    )
                }

        list_values = [value for value in payload.values() if isinstance(value, list)]
        if len(list_values) == 1 and get_origin(field_info.annotation) is list:
            return {
                field_name: self._normalize_field_value(
                    list_values[0],
                    field_info.annotation,
                    messages,
                )
            }

        return payload

    def _normalize_field_value(self, value: Any, annotation: Any, messages: list[Message]) -> Any:
        origin = get_origin(annotation)
        args = get_args(annotation)
        if origin is list and args and isinstance(value, list):
            item_model = args[0]
            if isinstance(item_model, type) and issubclass(item_model, BaseModel):
                return [
                    self._normalize_model_dict(item, item_model, messages) if isinstance(item, dict) else item
                    for item in value
                ]
        return value

    def _normalize_model_dict(
        self,
        payload: dict[str, Any],
        model: type[BaseModel],
        messages: list[Message],
    ) -> dict[str, Any]:
        normalized = dict(payload)
        for field_name in model.model_fields:
            if field_name in normalized:
                continue
            for candidate in _alias_candidates(field_name):
                if candidate in normalized:
                    normalized[field_name] = normalized.pop(candidate)
                    break
        if model.__name__ == "ExtractedEntity":
            _normalize_extracted_entity(normalized, messages)
        return normalized


def _to_camel_case(value: str) -> str:
    parts = value.split("_")
    if not parts:
        return value
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def _alias_candidates(field_name: str) -> list[str]:
    candidates = [
        field_name,
        field_name.replace("_", ""),
        _to_camel_case(field_name),
    ]
    if field_name == "name":
        candidates.extend(["entity_name", "node_name", "text", "entity"])
    if field_name == "source_entity_name":
        candidates.extend(["source_name", "source"])
    if field_name == "target_entity_name":
        candidates.extend(["target_name", "target"])
    return candidates


def _normalize_extracted_entity(payload: dict[str, Any], messages: list[Message]) -> None:
    if "entity_type_id" in payload:
        return

    raw_type = payload.pop("type", None) or payload.pop("entity_type", None) or payload.pop("entity_type_name", None)
    if raw_type is None:
        payload["entity_type_id"] = 0
        return

    entity_type_map = _extract_entity_type_map(messages)
    normalized_type = str(raw_type).strip().lower()
    payload["entity_type_id"] = entity_type_map.get(normalized_type, _fallback_entity_type_id(normalized_type, entity_type_map))


def _extract_entity_type_map(messages: list[Message]) -> dict[str, int]:
    combined = "\n".join(message.content for message in messages)
    match = re.search(r"<ENTITY TYPES>\s*(.*?)\s*</ENTITY TYPES>", combined, flags=re.DOTALL)
    if not match:
        return {}

    try:
        entries = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}

    mapping: dict[str, int] = {}
    for entry in entries:
        name = str(entry.get("entity_type_name", "")).strip()
        if not name:
            continue
        mapping[name.lower()] = int(entry.get("entity_type_id", 0))
    return mapping


def _fallback_entity_type_id(normalized_type: str, entity_type_map: dict[str, int]) -> int:
    if normalized_type in {"person", "human", "individual"} and "person" in entity_type_map:
        return entity_type_map["person"]
    if normalized_type in {"organization", "org", "company"} and "organization" in entity_type_map:
        return entity_type_map["organization"]
    return 0


def build_graph_driver(settings: GraphServiceSettings) -> FalkorDriver:
    """Build the FalkorDB driver used by Graphiti."""
    patch_falkor_property_serialization()
    patch_graphiti_edge_resolution_runtime()
    with _disable_falkor_auto_index_task():
        return FalkorDriver(
            host=settings.falkordb_host,
            port=settings.falkordb_port,
            username=settings.falkordb_username or None,
            password=settings.falkordb_password or None,
            database=settings.falkordb_database,
        )


@contextmanager
def _disable_falkor_auto_index_task():
    """Prevent FalkorDriver from scheduling a duplicate background index task during init."""
    original_get_running_loop = falkordb_driver_module.asyncio.get_running_loop

    def _raise_no_loop():
        raise RuntimeError("auto index task disabled")

    falkordb_driver_module.asyncio.get_running_loop = _raise_no_loop
    try:
        yield
    finally:
        falkordb_driver_module.asyncio.get_running_loop = original_get_running_loop


def patch_graphiti_edge_resolution_runtime() -> None:
    """Limit Graphiti edge-resolution concurrency and degrade timed-out searches."""
    global _GRAPHITI_EDGE_RUNTIME_PATCHED
    if _GRAPHITI_EDGE_RUNTIME_PATCHED:
        return

    original_semaphore_gather = edge_operations_module.semaphore_gather
    original_search = edge_operations_module.search

    async def patched_semaphore_gather(*coroutines, max_coroutines=None):
        bounded = max_coroutines if max_coroutines is not None else EDGE_RESOLUTION_MAX_CONCURRENCY
        return await original_semaphore_gather(*coroutines, max_coroutines=bounded)

    async def patched_search(*args, **kwargs):
        try:
            return await original_search(*args, **kwargs)
        except (
            TimeoutError,
            httpx.TimeoutException,
            openai.APITimeoutError,
            openai.APIConnectionError,
        ) as exc:
            logger.warning("Graphiti edge search degraded after timeout: %s", exc)
            return SearchResults()

    edge_operations_module.semaphore_gather = patched_semaphore_gather
    edge_operations_module.search = patched_search
    _GRAPHITI_EDGE_RUNTIME_PATCHED = True


def patch_falkor_property_serialization() -> None:
    """Patch Graphiti Falkor save paths so nested attribute values become primitive-safe."""
    global _FALKOR_PATCHED
    if _FALKOR_PATCHED:
        return

    original_node_save_bulk = FalkorEntityNodeOperations.save_bulk
    original_edge_save_bulk = FalkorEntityEdgeOperations.save_bulk
    original_node_save = FalkorEntityNodeOperations.save
    original_edge_save = FalkorEntityEdgeOperations.save
    original_bulk_add_nodes_and_edges = bulk_utils_module.add_nodes_and_edges_bulk

    async def patched_node_save_bulk(self, executor, nodes, tx=None, batch_size=100):
        sanitized_nodes = [_clone_with_safe_attributes(node) for node in nodes]
        return await original_node_save_bulk(self, executor, sanitized_nodes, tx=tx, batch_size=batch_size)

    async def patched_edge_save_bulk(self, executor, edges, tx=None, batch_size=100):
        sanitized_edges = [_clone_with_safe_attributes(edge) for edge in edges]
        return await original_edge_save_bulk(self, executor, sanitized_edges, tx=tx, batch_size=batch_size)

    async def patched_node_save(self, executor, node, tx=None):
        return await original_node_save(self, executor, _clone_with_safe_attributes(node), tx=tx)

    async def patched_edge_save(self, executor, edge, tx=None):
        return await original_edge_save(self, executor, _clone_with_safe_attributes(edge), tx=tx)

    async def patched_bulk_add_nodes_and_edges(
        driver,
        episodic_nodes,
        episodic_edges,
        entity_nodes,
        entity_edges,
        embedder,
    ):
        sanitized_nodes = [_clone_with_safe_attributes(node) for node in entity_nodes]
        sanitized_edges = [_clone_with_safe_attributes(edge) for edge in entity_edges]
        return await original_bulk_add_nodes_and_edges(
            driver,
            episodic_nodes,
            episodic_edges,
            sanitized_nodes,
            sanitized_edges,
            embedder,
        )

    FalkorEntityNodeOperations.save_bulk = patched_node_save_bulk
    FalkorEntityEdgeOperations.save_bulk = patched_edge_save_bulk
    FalkorEntityNodeOperations.save = patched_node_save
    FalkorEntityEdgeOperations.save = patched_edge_save
    bulk_utils_module.add_nodes_and_edges_bulk = patched_bulk_add_nodes_and_edges
    graphiti_module.add_nodes_and_edges_bulk = patched_bulk_add_nodes_and_edges
    _FALKOR_PATCHED = True


def _clone_with_safe_attributes(item: Any) -> Any:
    if not hasattr(item, "attributes"):
        return item
    cloned = item.model_copy(deep=True) if hasattr(item, "model_copy") else item
    raw_attributes = getattr(cloned, "attributes", None) or {}
    setattr(cloned, "attributes", _make_falkor_attributes_safe(raw_attributes))
    return cloned


def _make_falkor_attributes_safe(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: _make_falkor_value_safe(value) for key, value in payload.items()}


def _make_falkor_value_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        if all(isinstance(item, (str, int, float, bool)) or item is None for item in value):
            return value
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, tuple):
        if all(isinstance(item, (str, int, float, bool)) or item is None for item in value):
            return list(value)
        return json.dumps(list(value), ensure_ascii=False, default=str)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def build_llm_client(settings: GraphServiceSettings) -> OpenAIGenericClient:
    """Build the OpenAI-compatible LLM client used by Graphiti extraction."""
    config = LLMConfig(
        api_key=settings.graph_llm_api_key or "",
        base_url=_clean_base_url(settings.graph_llm_base_url),
        model=settings.graph_llm_model,
        temperature=COMPAT_LLM_TEMPERATURE,
        max_tokens=COMPAT_LLM_MAX_TOKENS,
    )
    client = AsyncOpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=COMPAT_LLM_TIMEOUT_SECONDS,
        max_retries=0,
    )
    return StructuredOutputCompatClient(
        config=config,
        client=client,
        max_tokens=COMPAT_LLM_MAX_TOKENS,
    )


def build_embedder(settings: GraphServiceSettings) -> OpenAIEmbedder:
    """Build the OpenAI-compatible embedder used by Graphiti."""
    config = OpenAIEmbedderConfig(
        api_key=settings.graph_embedding_api_key or "",
        base_url=_clean_base_url(settings.graph_embedding_base_url),
        embedding_model=settings.graph_embedding_model,
        embedding_dim=settings.graph_embedding_dim,
    )
    client = AsyncOpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=COMPAT_EMBEDDING_TIMEOUT_SECONDS,
        max_retries=0,
    )
    return OpenAIEmbedder(config=config, client=client)


def build_reranker(settings: GraphServiceSettings) -> OpenAIRerankerClient | None:
    """Build the optional OpenAI-compatible reranker for v1 search paths."""
    provider_name = settings.graph_reranker_provider.strip().lower()
    if provider_name in {"", "disabled", "custom"}:
        return None

    model_name = settings.graph_reranker_model.strip()
    if provider_name != "openai_compat" or not model_name:
        return None

    config = LLMConfig(
        api_key=settings.graph_reranker_api_key or "",
        base_url=_clean_base_url(settings.graph_reranker_base_url),
        model=model_name,
    )
    return OpenAIRerankerClient(config=config)
