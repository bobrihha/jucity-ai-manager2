from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KBDocument:
    file_path: str
    text: str


def load_kb_markdown(root: Path) -> list[KBDocument]:
    docs: list[KBDocument] = []
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.as_posix()
        docs.append(KBDocument(file_path=rel, text=text))
    return docs

