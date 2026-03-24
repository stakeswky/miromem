"""Tests for Thinker config wiring and in-memory job registry."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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
    store.mark_running(job.job_id)
    store.mark_failed(job.job_id, error_code="upstream_error", error_message="timeout")
    retried = store.retry_job(job.job_id)
    assert retried.status == "created"

    completed = store.create_job(mode="topic_only", research_direction="CPI outlook")
    store.mark_running(completed.job_id)
    store.mark_succeeded(completed.job_id)
    with pytest.raises(ValueError):
        store.retry_job(completed.job_id)


def test_illegal_state_transition_raises_value_error():
    store = InMemoryThinkerJobStore()
    job = store.create_job(mode="topic_only", research_direction="Fed outlook")

    with pytest.raises(ValueError):
        store.mark_succeeded(job.job_id)


def test_failed_job_can_be_skipped():
    store = InMemoryThinkerJobStore()
    job = store.create_job(mode="topic_only", research_direction="Fed outlook")

    store.mark_running(job.job_id)
    store.mark_failed(job.job_id, error_code="upstream_error", error_message="timeout")
    skipped = store.mark_skipped(job.job_id)

    assert skipped.status == "skipped"


def test_external_mutation_does_not_change_stored_job():
    store = InMemoryThinkerJobStore()
    job = store.create_job(mode="topic_only", research_direction="Fed outlook")

    job.status = "succeeded"
    job.mode = "upload"

    stored = store.get_job(job.job_id)
    assert stored.status == "created"
    assert stored.mode == "topic_only"

    stored.status = "failed"
    assert store.get_job(job.job_id).status == "created"


def test_invalid_mode_is_rejected():
    store = InMemoryThinkerJobStore()

    with pytest.raises(ValidationError):
        store.create_job(mode="invalid", research_direction="Fed outlook")


def test_load_config_includes_thinker_settings(monkeypatch):
    monkeypatch.setenv("THINKER_LLM_BASE_URL", "https://api.example.com/v1")
    config = load_config()
    assert config.thinker.llm_base_url == "https://api.example.com/v1"


def test_load_config_thinker_settings_do_not_fallback_to_global_llm(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "global-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://global.example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "gpt-global")
    monkeypatch.delenv("THINKER_LLM_API_KEY", raising=False)
    monkeypatch.delenv("THINKER_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("THINKER_LLM_MODEL", raising=False)

    config = load_config()

    assert config.thinker.llm_api_key == ""
    assert config.thinker.llm_base_url == ""
    assert config.thinker.llm_model == ""
