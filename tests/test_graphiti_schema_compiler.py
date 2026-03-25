"""Tests for compiling MiroFish ontology JSON into Graphiti schema models."""

from __future__ import annotations

from pydantic import BaseModel

from miromem.graph_service.domain.schema_compiler import CompiledOntology, compile_ontology


def test_compile_ontology_returns_entity_and_edge_maps():
    ontology = {
        "entity_types": [
            {
                "name": "Politician",
                "description": "Elected public official",
                "attributes": [
                    {
                        "name": "party",
                        "description": "Political party affiliation",
                        "type": "text",
                    }
                ],
            },
            {
                "name": "MediaOutlet",
                "description": "News organization or publisher",
                "attributes": [
                    {
                        "name": "coverage_area",
                        "description": "Primary topic coverage area",
                        "type": "text",
                    }
                ],
            },
        ],
        "edge_types": [
            {
                "name": "ENDORSES",
                "description": "Publicly supports another actor",
                "attributes": [
                    {
                        "name": "endorsement_type",
                        "description": "Type of endorsement being expressed",
                        "type": "text",
                    }
                ],
                "source_targets": [
                    {"source": "Politician", "target": "Politician"},
                    {"source": "MediaOutlet", "target": "Politician"},
                ],
            }
        ],
    }

    compiled = compile_ontology(ontology)

    assert isinstance(compiled, CompiledOntology)
    assert "Politician" in compiled.entity_types
    assert "ENDORSES" in compiled.edge_types
    assert issubclass(compiled.entity_types["Politician"], BaseModel)
    assert issubclass(compiled.edge_types["ENDORSES"], BaseModel)
    assert compiled.entity_types["Politician"].__name__ == "Politician"
    assert compiled.edge_types["ENDORSES"].__name__ == "ENDORSES"
    assert compiled.entity_types["Politician"].__doc__ == "Elected public official"
    assert compiled.edge_types["ENDORSES"].__doc__ == "Publicly supports another actor"
    assert (
        compiled.entity_types["Politician"].model_fields["party"].description
        == "Political party affiliation"
    )
    assert (
        compiled.edge_types["ENDORSES"].model_fields["endorsement_type"].description
        == "Type of endorsement being expressed"
    )
    assert compiled.edge_type_map[("Politician", "Politician")] == ["ENDORSES"]
    assert compiled.edge_type_map[("MediaOutlet", "Politician")] == ["ENDORSES"]


def test_compile_ontology_keeps_edge_type_order_per_signature():
    ontology = {
        "entity_types": [
            {"name": "Person", "description": "Natural person", "attributes": []},
            {"name": "Organization", "description": "Formal organization", "attributes": []},
        ],
        "edge_types": [
            {
                "name": "SUPPORTS",
                "description": "Shows support for another entity",
                "attributes": [],
                "source_targets": [{"source": "Person", "target": "Organization"}],
            },
            {
                "name": "OPPOSES",
                "description": "Shows opposition to another entity",
                "attributes": [],
                "source_targets": [{"source": "Person", "target": "Organization"}],
            },
        ],
    }

    compiled = compile_ontology(ontology)

    assert compiled.edge_type_map[("Person", "Organization")] == ["SUPPORTS", "OPPOSES"]
