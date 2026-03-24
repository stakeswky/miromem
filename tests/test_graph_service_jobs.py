"""Tests for graph-service job state storage."""

from __future__ import annotations

from miromem.graph_service.storage.job_store import InMemoryGraphJobStore


def test_job_store_tracks_degraded_state():
    store = InMemoryGraphJobStore()

    job = store.create_job(job_type="build_graph", graph_id="mirofish_test")
    store.mark_degraded(job.job_id, reason="reranker_unavailable")
    current = store.get_job(job.job_id)

    assert current is not None
    assert current.status == "degraded"
    assert current.degraded_reason == "reranker_unavailable"
