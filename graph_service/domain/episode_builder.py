"""Helpers for turning source documents into Graphiti episodes."""

from __future__ import annotations

from datetime import datetime

from graphiti_core.nodes import EpisodeType
from graphiti_core.utils.bulk_utils import RawEpisode

from miromem.graph_service.models import utc_now


def chunk_text(document_text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split document text into overlapping chunks."""
    if not document_text:
        return []

    normalized_chunk_size = max(1, chunk_size)
    step = max(1, normalized_chunk_size - max(0, chunk_overlap))
    chunks: list[str] = []

    for start in range(0, len(document_text), step):
        chunk = document_text[start : start + normalized_chunk_size].strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def build_document_episodes(
    *,
    graph_name: str,
    document_text: str,
    chunk_size: int,
    chunk_overlap: int,
    source_description: str = "document_text",
    reference_time: datetime | None = None,
) -> list[RawEpisode]:
    """Build RawEpisode entries for a graph build request."""
    timestamp = reference_time or utc_now()
    return [
        RawEpisode(
            name=f"{graph_name} chunk {index}",
            content=chunk,
            source_description=source_description,
            source=EpisodeType.text,
            reference_time=timestamp,
        )
        for index, chunk in enumerate(chunk_text(document_text, chunk_size, chunk_overlap), start=1)
    ]
