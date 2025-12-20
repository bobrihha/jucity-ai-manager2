from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    file_path: str
    heading: str | None
    text: str


def _extract_headings(markdown: str) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    lines = markdown.splitlines()
    offset = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            if title:
                headings.append((offset, title))
        offset += len(line) + 1
    return headings


def _heading_for_offset(headings: list[tuple[int, str]], offset: int) -> str | None:
    current: str | None = None
    for pos, title in headings:
        if pos <= offset:
            current = title
        else:
            break
    return current


def chunk_markdown(
    *,
    file_path: str,
    markdown: str,
    chunk_size: int = 900,
    overlap: int = 150,
) -> list[Chunk]:
    text = markdown.strip()
    if not text:
        return []

    headings = _extract_headings(markdown)
    chunks: list[Chunk] = []

    start = 0
    idx = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)

        if end < len(text):
            nl = text.rfind("\n", start, end)
            if nl > start + int(chunk_size * 0.6):
                end = nl

        chunk_text = text[start:end].strip()
        heading = _heading_for_offset(headings, start)
        chunk_id = f"{file_path}::chunk::{idx}"
        chunks.append(Chunk(chunk_id=chunk_id, file_path=file_path, heading=heading, text=chunk_text))

        if end >= len(text):
            break
        start = max(0, end - overlap)
        idx += 1

    return chunks

