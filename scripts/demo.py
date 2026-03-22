#!/usr/bin/env python3
"""MiroMem end-to-end demo — exercises the full pipeline via the Gateway API."""

from __future__ import annotations

import asyncio
import json
import sys

import httpx

GATEWAY = "http://localhost:8000"

SAMPLE_ARTICLE = (
    "OpenAI announced GPT-5 at their spring developer conference in San Francisco. "
    "CEO Sam Altman demonstrated new multimodal capabilities including real-time video "
    "understanding and advanced reasoning. The model showed significant improvements in "
    "mathematical problem-solving and code generation. Google DeepMind responded by "
    "releasing Gemini Ultra 2.0 the following week, featuring a 2-million token context "
    "window. Microsoft integrated GPT-5 into Copilot across all Office products. "
    "Anthropic's Claude 4 was noted for its strong performance in safety benchmarks. "
    "The AI industry saw record venture capital investment of $120 billion in Q1 2026, "
    "with enterprise adoption accelerating across healthcare, finance, and manufacturing."
)


def _print(label: str, data) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, default=str)[:2000])
    else:
        print(str(data)[:2000])


async def main() -> None:
    async with httpx.AsyncClient(base_url=GATEWAY, timeout=120.0) as c:

        # 0. Health check
        print("Checking gateway health...")
        r = await c.get("/health")
        _print("Health", r.json())
        if r.status_code != 200:
            print("Gateway not healthy, aborting.")
            sys.exit(1)

        # 1. Build knowledge graph from sample article
        print("\n>>> Step 1: Ingesting article into Knowledge Graph...")
        r = await c.post(
            "/api/v1/graph/ingest",
            json={"texts": [SAMPLE_ARTICLE], "chunk_size": 512},
        )
        graph_result = r.json()
        _print("Graph Ingest Result", graph_result)
        entities = graph_result.get("entities", [])
        print(f"  Extracted {len(entities)} entities, "
              f"{len(graph_result.get('edges', []))} edges")

        # 2. Search the knowledge graph
        print("\n>>> Step 2: Searching knowledge graph for 'AI investment'...")
        r = await c.post(
            "/api/v1/graph/search",
            json={"query": "AI investment", "limit": 5},
        )
        _print("Graph Search", r.json())

        # 3. Get entity context
        if entities:
            name = entities[0].get("name", "OpenAI")
            print(f"\n>>> Step 3: Getting context for entity '{name}'...")
            r = await c.get(f"/api/v1/graph/context/{name}")
            _print("Entity Context", r.json())

        # 4. Store a memory in EverMemOS via bridge
        print("\n>>> Step 4: Storing episodic memory in EverMemOS...")
        r = await c.post(
            "/api/v1/memories",
            json={
                "user_id": "demo-agent-001",
                "content": "Observed rapid AI industry growth with $120B VC investment in Q1 2026",
                "memory_type": "EpisodicMemory",
                "metadata": {"role": "ai", "sim_id": "sim-demo-001"},
            },
        )
        _print("Memory Stored", r.json() if r.status_code == 200 else r.text)

        # 5. Mark memories as cross-sim available
        print("\n>>> Step 5: Marking memories for cross-simulation use...")
        r = await c.post(
            "/api/v1/evolution/mark",
            json={
                "sim_id": "sim-demo-001",
                "memory_ids": ["mem-001", "mem-002"],
                "importance_scores": {"mem-001": 0.9, "mem-002": 0.7},
                "agent_id": "demo-agent-001",
                "topic_tags": ["AI", "investment", "industry"],
            },
        )
        _print("Cross-Sim Mark", r.json())

        # 6. Simulate a second simulation — inject historical memory
        print("\n>>> Step 6: Injecting historical memory for new simulation...")
        r = await c.post(
            "/api/v1/evolution/inject",
            json={
                "agent_id": "demo-agent-001",
                "agent_identity": "demo-agent-001",
                "sim_context": "Predict AI market trends for Q2 2026",
                "top_k": 5,
            },
        )
        _print("Memory Injection", r.json())

        # 7. Check evolution history
        print("\n>>> Step 7: Checking agent evolution history...")
        r = await c.get("/api/v1/evolution/history/demo-agent-001")
        _print("Evolution History", r.json())

        # 8. Validate foresight predictions
        print("\n>>> Step 8: Validating foresight predictions...")
        r = await c.post("/api/v1/evolution/validate/sim-demo-001")
        _print("Foresight Validation", r.json())

        # 9. List simulations
        print("\n>>> Step 9: Listing simulations...")
        r = await c.get("/api/v1/evolution/simulations")
        _print("Simulations", r.json())

        print("\n" + "=" * 60)
        print("  Demo complete!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
