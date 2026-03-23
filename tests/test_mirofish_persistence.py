from __future__ import annotations

from pathlib import Path


def test_mirofish_upload_volume_targets_backend_uploads_directory() -> None:
    compose_path = Path(__file__).resolve().parents[1] / "docker-compose.yaml"
    compose_text = compose_path.read_text(encoding="utf-8")

    assert "- mirofish_uploads:/app/backend/uploads" in compose_text
    assert "- mirofish_uploads:/app/uploads" not in compose_text
