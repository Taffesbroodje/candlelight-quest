from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


SEED_DIR = Path(__file__).resolve().parent
CHUNK_TARGET = 500  # approximate character count per chunk

_PARAGRAPH_SEP = chr(10) + chr(10)


def _chunk_paragraphs(text: str, target: int = CHUNK_TARGET) -> list[str]:
    """Split *text* into chunks of roughly *target* characters at paragraph
    boundaries.  Paragraphs shorter than *target* are merged together;
    paragraphs longer than *target* are kept whole rather than being split
    mid-sentence.
    """
    paragraphs = [p.strip() for p in text.split(_PARAGRAPH_SEP) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current and current_len + para_len > target:
            chunks.append(_PARAGRAPH_SEP.join(current))
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len

    if current:
        chunks.append(_PARAGRAPH_SEP.join(current))

    return chunks


def _content_id(text: str) -> str:
    """Deterministic document ID derived from the content hash."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _category_from_filename(path: Path) -> str:
    """Derive a human-readable category from the markdown filename."""
    return path.stem.replace("_", " ")


def load_seed_documents() -> list[dict[str, Any]]:
    """Read every ``.md`` file in the seed_data directory and return a flat
    list of chunk dicts ready for :pymethod:`Indexer.index_seed_data`.

    Each dict contains:
    - **content** -- the text chunk
    - **category** -- derived from the source filename
    - **id** -- a deterministic hash of the content
    """
    documents: list[dict[str, Any]] = []

    for md_path in sorted(SEED_DIR.glob("*.md")):
        raw = md_path.read_text(encoding="utf-8")
        category = _category_from_filename(md_path)
        for chunk in _chunk_paragraphs(raw):
            documents.append(
                {
                    "content": chunk,
                    "category": category,
                    "id": _content_id(chunk),
                }
            )

    return documents
