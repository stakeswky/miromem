"""Tests for Thinker config wiring and in-memory job registry."""

from __future__ import annotations

import pytest

from miromem.config.settings import load_config
from miromem.thinker.jobs import InMemoryThinkerJobStore


def test_job_store_creates_pending_job():
    store = InMemoryThinkerJobStore()
    job = store.create_job(mode="topic_only", research_direction="Fed outlook")
    assert job.status == "created"
    assert job.mode == "topic_only"


def test_failed_job_can_be_retried_but_succeeded_job_cannot():
    store = InMemoryThinkerJobStore()
    job = store.create_job(mode="topic_only", research_direction="Fed outlook")
    store.mark_failed(job.job_id, error_code="upstream_error", error_message="timeout")
    retried = store.retry_job(job.job_id)
    assert retried.status == "created"

    completed = store.create_job(mode="topic_only", research_direction="CPI outlook")
    store.mark_succeeded(completed.job_id)
    with pytest.raises(ValueError):
        store.retry_job(completed.job_id)


def test_load_config_includes_thinker_settings(monkeypatch):
    monkeypatch.setenv("THINKER_LLM_BASE_URL", "https://api.example.com/v1")
    config = load_config()
    assert config.thinker.llm_base_url == "https://api.example.com/v1"
