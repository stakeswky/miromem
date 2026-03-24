"""Contract tests for Graphiti snapshot serialization."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode

from miromem.graph_service.domain.snapshot_serializer import serialize_snapshot


def test_serialize_snapshot_matches_mirofish_contract():
    created_at = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    refreshed_at = "2026-03-24T12:30:00+00:00"
    nodes = [
        EntityNode(
            uuid="node-1",
            name="Alice",
            group_id="mirofish_demo",
            labels=["Entity", "Person"],
            created_at=created_at,
            summary="A market analyst",
            attributes={"region": "US"},
        ),
        EntityNode(
            uuid="node-2",
            name="California",
            group_id="mirofish_demo",
            labels=["Entity", "Place"],
            created_at=created_at,
            summary="A state",
            attributes={},
        ),
    ]
    edges = [
        EntityEdge(
            uuid="edge-1",
            group_id="mirofish_demo",
            source_node_uuid="node-1",
            target_node_uuid="node-2",
            created_at=created_at,
            name="CAMPAIGNS_IN",
            fact="Alice is campaigning in California.",
            valid_at=created_at,
            invalid_at=None,
            expired_at=None,
            episodes=["episode-1"],
            attributes={"confidence": "high"},
        )
    ]

    payload = serialize_snapshot(
        nodes=nodes,
        edges=edges,
        graph_id="mirofish_demo",
        stale=False,
        last_refreshed_at=refreshed_at,
    )

    assert payload == {
        "graph_id": "mirofish_demo",
        "node_count": 2,
        "edge_count": 1,
        "stale": False,
        "last_refreshed_at": refreshed_at,
        "nodes": [
            {
                "uuid": "node-1",
                "name": "Alice",
                "labels": ["Entity", "Person"],
                "summary": "A market analyst",
                "attributes": {"region": "US"},
                "created_at": "2026-03-24T12:00:00+00:00",
            },
            {
                "uuid": "node-2",
                "name": "California",
                "labels": ["Entity", "Place"],
                "summary": "A state",
                "attributes": {},
                "created_at": "2026-03-24T12:00:00+00:00",
            },
        ],
        "edges": [
            {
                "uuid": "edge-1",
                "name": "CAMPAIGNS_IN",
                "fact": "Alice is campaigning in California.",
                "fact_type": "CAMPAIGNS_IN",
                "source_node_uuid": "node-1",
                "target_node_uuid": "node-2",
                "source_node_name": "Alice",
                "target_node_name": "California",
                "attributes": {"confidence": "high"},
                "created_at": "2026-03-24T12:00:00+00:00",
                "valid_at": "2026-03-24T12:00:00+00:00",
                "invalid_at": None,
                "expired_at": None,
                "episodes": ["episode-1"],
            }
        ],
    }


def test_serialize_snapshot_preserves_fact_type_and_episode_ids_aliases():
    payload = serialize_snapshot(
        graph_id="mirofish_demo",
        stale=True,
        last_refreshed_at="2026-03-24T13:00:00+00:00",
        nodes=[
            {
                "uuid_": "node-1",
                "name": "Alice",
                "labels": ["Entity", "Person"],
                "summary": "A market analyst",
                "attributes": {},
                "created_at": "2026-03-24T12:00:00+00:00",
            },
            {
                "uuid_": "node-2",
                "name": "Bob",
                "labels": ["Entity", "Person"],
                "summary": "A campaign manager",
                "attributes": {},
                "created_at": "2026-03-24T12:05:00+00:00",
            },
        ],
        edges=[
            SimpleNamespace(
                uuid_="edge-2",
                name="",
                fact_type="ALLY_OF",
                fact="Alice works closely with Bob.",
                source_node_uuid="node-1",
                target_node_uuid="node-2",
                attributes={"confidence": "medium"},
                created_at="2026-03-24T12:10:00+00:00",
                valid_at=None,
                invalid_at=None,
                expired_at=None,
                episode_ids=["episode-2"],
            )
        ],
    )

    assert payload["stale"] is True
    assert payload["edges"] == [
        {
            "uuid": "edge-2",
            "name": "",
            "fact": "Alice works closely with Bob.",
            "fact_type": "ALLY_OF",
            "source_node_uuid": "node-1",
            "target_node_uuid": "node-2",
            "source_node_name": "Alice",
            "target_node_name": "Bob",
            "attributes": {"confidence": "medium"},
            "created_at": "2026-03-24T12:10:00+00:00",
            "valid_at": None,
            "invalid_at": None,
            "expired_at": None,
            "episodes": ["episode-2"],
        }
    ]
