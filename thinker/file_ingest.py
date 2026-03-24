"""Gateway-side upload extraction for Thinker inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from miromem.thinker.models import ThinkerUploadedFile


class UploadLike(Protocol):
    """Minimal async upload contract used by the gateway."""

    filename: str | None

    async def read(self, size: int = -1) -> bytes:
        """Read the upload contents."""


_SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}


async def extract_uploads(files: list[UploadLike]) -> list[ThinkerUploadedFile]:
    """Extract normalized text payloads from uploaded files."""
    extracted: list[ThinkerUploadedFile] = []
    for file in files:
        name = file.filename or "upload"
        payload = await file.read()
        extracted.append(
            ThinkerUploadedFile(
                name=name,
                text=extract_text(name=name, payload=payload),
            )
        )
    return extracted


def extract_text(*, name: str, payload: bytes) -> str:
    """Extract text from a supported upload payload."""
    suffix = Path(name).suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported upload type: {suffix or 'unknown'}")

    if suffix == ".pdf":
        return _extract_pdf_text(payload)

    return _decode_text_payload(payload)


def _extract_pdf_text(payload: bytes) -> str:
    import fitz

    pages: list[str] = []
    with fitz.open(stream=payload, filetype="pdf") as document:
        for page in document:
            text = page.get_text().strip()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def _decode_text_payload(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")
