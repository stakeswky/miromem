"""Compile ontology JSON into Graphiti runtime schema objects."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, NamedTuple

from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode
from pydantic import BaseModel, Field, create_model

ENTITY_RESERVED_FIELD_NAMES = frozenset(name.lower() for name in EntityNode.model_fields)
EDGE_RESERVED_FIELD_NAMES = frozenset(name.lower() for name in EntityEdge.model_fields)

ATTRIBUTE_TYPE_MAP: dict[str, type[Any]] = {
    "bool": bool,
    "boolean": bool,
    "float": float,
    "int": int,
    "integer": int,
    "number": float,
    "string": str,
    "text": str,
}


class CompiledOntology(NamedTuple):
    """Runtime Graphiti schema compiled from ontology JSON."""

    entity_types: dict[str, type[BaseModel]]
    edge_types: dict[str, type[BaseModel]]
    edge_type_map: dict[tuple[str, str], list[str]]


def compile_ontology(ontology: Mapping[str, Any]) -> CompiledOntology:
    """Compile ontology JSON into the Graphiti runtime schema contract."""
    entity_definitions = ontology.get("entity_types", [])
    edge_definitions = ontology.get("edge_types", [])

    entity_types = _compile_models(
        definitions=entity_definitions,
        default_suffix="entity",
        reserved_field_names=ENTITY_RESERVED_FIELD_NAMES,
    )
    edge_types = _compile_models(
        definitions=edge_definitions,
        default_suffix="relationship",
        reserved_field_names=EDGE_RESERVED_FIELD_NAMES,
    )

    return CompiledOntology(
        entity_types=entity_types,
        edge_types=edge_types,
        edge_type_map=_compile_edge_type_map(edge_definitions),
    )


def _compile_models(
    definitions: Iterable[Mapping[str, Any]],
    default_suffix: str,
    reserved_field_names: frozenset[str],
) -> dict[str, type[BaseModel]]:
    models: dict[str, type[BaseModel]] = {}

    for definition in definitions:
        name = definition["name"]
        description = definition.get("description") or f"A {name} {default_suffix}."
        models[name] = _build_model(
            name=name,
            description=description,
            attributes=definition.get("attributes", []),
            reserved_field_names=reserved_field_names,
        )

    return models


def _build_model(
    name: str,
    description: str,
    attributes: Iterable[Mapping[str, Any]],
    reserved_field_names: frozenset[str],
) -> type[BaseModel]:
    fields: dict[str, tuple[type[Any] | None, Field]] = {}

    for attribute in attributes:
        attribute_name = _safe_attribute_name(attribute["name"], reserved_field_names)
        attribute_type = _resolve_attribute_type(attribute.get("type"))
        attribute_description = attribute.get("description") or attribute["name"]
        fields[attribute_name] = (
            attribute_type | None,
            Field(default=None, description=attribute_description),
        )

    model = create_model(name, __base__=BaseModel, **fields)
    model.__doc__ = description
    model.__module__ = __name__
    return model


def _compile_edge_type_map(
    edge_definitions: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], list[str]]:
    edge_type_map: dict[tuple[str, str], list[str]] = {}

    for edge_definition in edge_definitions:
        edge_name = edge_definition["name"]
        for source_target in edge_definition.get("source_targets", []):
            signature = (
                source_target.get("source", "Entity"),
                source_target.get("target", "Entity"),
            )
            allowed_edge_names = edge_type_map.setdefault(signature, [])
            if edge_name not in allowed_edge_names:
                allowed_edge_names.append(edge_name)

    return edge_type_map


def _resolve_attribute_type(type_name: Any) -> type[Any]:
    if not isinstance(type_name, str):
        return str

    return ATTRIBUTE_TYPE_MAP.get(type_name.lower(), str)


def _safe_attribute_name(attribute_name: str, reserved_field_names: frozenset[str]) -> str:
    if attribute_name.lower() in reserved_field_names:
        return f"entity_{attribute_name}"

    return attribute_name
