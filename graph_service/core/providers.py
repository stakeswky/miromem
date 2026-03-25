"""Provider factory helpers for Graphiti service bootstrap."""

from __future__ import annotations

import json
import re
from typing import Any, get_args, get_origin

from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.falkordb.operations.entity_edge_ops import FalkorEntityEdgeOperations
from graphiti_core.driver.falkordb.operations.entity_node_ops import FalkorEntityNodeOperations
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client import LLMConfig
from graphiti_core.llm_client.config import ModelSize
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.prompts.models import Message
from pydantic import BaseModel

from miromem.graph_service.core.config import GraphServiceSettings


def _clean_base_url(value: str) -> str | None:
    """Normalize blank OpenAI-compatible base URLs to None."""
    cleaned = value.strip()
    return cleaned or None


_FALKOR_PATCHED = False


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
        payload = await super()._generate_response(
            normalized_messages,
            response_model=response_model,
            max_tokens=max_tokens,
            model_size=model_size,
        )
        if response_model is None:
            return payload
        return self._normalize_payload_shape(payload, response_model, normalized_messages)

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
    return FalkorDriver(
        host=settings.falkordb_host,
        port=settings.falkordb_port,
        username=settings.falkordb_username or None,
        password=settings.falkordb_password or None,
        database=settings.falkordb_database,
    )


def patch_falkor_property_serialization() -> None:
    """Patch Graphiti Falkor save paths so nested attribute values become primitive-safe."""
    global _FALKOR_PATCHED
    if _FALKOR_PATCHED:
        return

    original_node_save_bulk = FalkorEntityNodeOperations.save_bulk
    original_edge_save_bulk = FalkorEntityEdgeOperations.save_bulk
    original_node_save = FalkorEntityNodeOperations.save
    original_edge_save = FalkorEntityEdgeOperations.save

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

    FalkorEntityNodeOperations.save_bulk = patched_node_save_bulk
    FalkorEntityEdgeOperations.save_bulk = patched_edge_save_bulk
    FalkorEntityNodeOperations.save = patched_node_save
    FalkorEntityEdgeOperations.save = patched_edge_save
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
    )
    return StructuredOutputCompatClient(config=config)


def build_embedder(settings: GraphServiceSettings) -> OpenAIEmbedder:
    """Build the OpenAI-compatible embedder used by Graphiti."""
    config = OpenAIEmbedderConfig(
        api_key=settings.graph_embedding_api_key or "",
        base_url=_clean_base_url(settings.graph_embedding_base_url),
        embedding_model=settings.graph_embedding_model,
        embedding_dim=settings.graph_embedding_dim,
    )
    return OpenAIEmbedder(config=config)


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
