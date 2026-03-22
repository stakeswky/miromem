"""LLM-driven entity and relationship extraction from text."""

from __future__ import annotations

import json
import logging
from difflib import SequenceMatcher

from openai import AsyncOpenAI

from miromem.config.settings import load_config
from miromem.graph.models import Edge, Entity

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
You are an entity-relationship extraction engine.

Given the text below, extract all entities and relationships.

{ontology_section}

Return ONLY valid JSON matching this schema (no markdown fences):
{{
  "entities": [
    {{"name": "...", "entity_type": "...", "description": "..."}}
  ],
  "edges": [
    {{"source": "entity name", "target": "entity name", "relation_type": "...", "description": "..."}}
  ]
}}

Text:
{text}
"""


class EntityExtractor:
    """Extract entities and relationships from text using an LLM."""

    def __init__(
        self,
        *,
        entity_types: list[str] | None = None,
        similarity_threshold: float = 0.85,
    ) -> None:
        cfg = load_config()
        self._client = AsyncOpenAI(api_key=cfg.llm.api_key, base_url=cfg.llm.base_url)
        self._model = cfg.llm.model
        self._entity_types = entity_types
        self._sim_threshold = similarity_threshold

    async def extract(self, text: str) -> tuple[list[Entity], list[Edge]]:
        """Extract entities and edges from *text* via LLM."""
        ontology_section = ""
        if self._entity_types:
            ontology_section = f"Allowed entity types: {', '.join(self._entity_types)}\n"

        prompt = _EXTRACTION_PROMPT.format(ontology_section=ontology_section, text=text)

        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        raw = resp.choices[0].message.content or "{}"
        # strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON for entity extraction")
            return [], []

        # Build entities, deduplicating by name similarity
        entities: list[Entity] = []
        name_map: dict[str, Entity] = {}  # canonical name -> Entity

        for item in data.get("entities", []):
            name = item.get("name", "").strip()
            if not name:
                continue
            canonical = self._find_similar(name, name_map)
            if canonical is None:
                ent = Entity(
                    name=name,
                    entity_type=item.get("entity_type", "unknown"),
                    description=item.get("description", ""),
                )
                entities.append(ent)
                name_map[name.lower()] = ent
            # else: duplicate, skip

        # Build edges, resolving entity names to ids
        edges: list[Edge] = []
        for item in data.get("edges", []):
            src_name = item.get("source", "").strip()
            tgt_name = item.get("target", "").strip()
            src_key = self._find_similar(src_name, name_map) or src_name.lower()
            tgt_key = self._find_similar(tgt_name, name_map) or tgt_name.lower()
            src_ent = name_map.get(src_key)
            tgt_ent = name_map.get(tgt_key)
            if src_ent and tgt_ent:
                edges.append(
                    Edge(
                        source_entity_id=src_ent.id,
                        target_entity_id=tgt_ent.id,
                        relation_type=item.get("relation_type", "related_to"),
                        description=item.get("description", ""),
                    )
                )

        return entities, edges

    def _find_similar(self, name: str, name_map: dict[str, Entity]) -> str | None:
        """Return the canonical key if *name* is similar enough to an existing entry."""
        lower = name.lower()
        if lower in name_map:
            return lower
        for key in name_map:
            if SequenceMatcher(None, lower, key).ratio() >= self._sim_threshold:
                return key
        return None
