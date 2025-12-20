from __future__ import annotations

import os
from pathlib import Path
import re

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

from app.config import get_settings
from app.rag.answerer import OpenAIAnswerer, build_direct_context
from app.rag.embedder import OpenAIEmbedder
from app.rag.store_factory import get_store
from app.rag.prompts import SYSTEM_PROMPT_JUICY_V1


app = FastAPI(title="JuCity AI Manager", version="0.1.0")

_settings = get_settings()


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[str]


@app.get("/health")
def health() -> dict[str, str]:
    if _settings.vector_backend == "qdrant":
        try:
            store = get_store(_settings, vector_size=1)
            store.client.get_collections()  # type: ignore[attr-defined]
            return {"status": "ok", "backend": "qdrant"}
        except Exception:
            return {"status": "error", "backend": "qdrant"}

    if _settings.vector_backend == "chroma":
        try:
            from pathlib import Path

            Path(_settings.chroma_dir).mkdir(parents=True, exist_ok=True)
            return {"status": "ok", "backend": "chroma"}
        except Exception as exc:
            return {"status": "error", "backend": "chroma", "detail": f"{type(exc).__name__}: {exc}"}

    return {"status": "error", "backend": _settings.vector_backend, "detail": "unknown VECTOR_BACKEND"}


def _read_contacts() -> str:
    contacts_path = Path("kb/nn/core/contacts.md")
    if not contacts_path.exists():
        return ""
    return contacts_path.read_text(encoding="utf-8").strip()


def _fallback_answer_with_contacts(contacts_text: str) -> str:
    base = "Лучше уточнить у администратора/отдела праздников."
    if not contacts_text:
        return base
    return f"{base}\n\nКонтакты:\n{contacts_text}"


def _tokenize_for_overlap(text: str) -> set[str]:
    cleaned = re.sub(r"[^\w\s]+", " ", text.lower(), flags=re.UNICODE)
    tokens = [t for t in cleaned.split() if t]
    out: set[str] = set()
    for t in tokens:
        out.add(t)
        if t.isdigit():
            stripped = t.lstrip("0") or "0"
            out.add(stripped)
    return out


def _detect_intent(question: str) -> str:
    q = question.lower()

    if "1 января" in q or "31 декабря" in q or "до скольки" in q or "режим" in q or "работаете" in q:
        return "hours"
    if "скидк" in q or "льгот" in q or "овз" in q or "многодет" in q:
        return "discounts"
    if "vr" in q:
        return "vr"
    if "фиджитал" in q:
        return "phygital"
    if "торт" in q or "сладкий" in q:
        return "own_food_rules"
    if (
        "сколько стоит" in q
        or "цена" in q
        or "билет" in q
        or any(day in q for day in ["понедельник", "вторник", "сред", "четверг", "пятниц", "суббот", "воскрес"])
    ):
        return "prices"
    return "general"


def _allowed_files_for_intent(intent: str) -> set[str] | None:
    if intent == "hours":
        return {"kb/nn/core/hours.md", "kb/nn/core/contacts.md"}
    if intent == "prices":
        return {"kb/nn/tickets/prices.md", "kb/nn/tickets/free_entry.md"}
    if intent == "discounts":
        return {"kb/nn/tickets/discounts.md", "kb/nn/tickets/after_20.md"}
    if intent == "vr":
        return {"kb/nn/services/vr.md"}
    if intent == "phygital":
        return {"kb/nn/services/phygital.md"}
    if intent == "own_food_rules":
        return {"kb/nn/food/own_food_rules.md", "kb/nn/parties/birthday.md"}
    return None


def _router_fallback_files(intent: str) -> list[str]:
    if intent == "hours":
        return ["kb/nn/core/hours.md", "kb/nn/core/contacts.md"]
    if intent == "prices":
        return ["kb/nn/tickets/prices.md", "kb/nn/core/contacts.md"]
    if intent == "discounts":
        return ["kb/nn/tickets/discounts.md", "kb/nn/core/contacts.md"]
    if intent == "vr":
        return ["kb/nn/services/vr.md", "kb/nn/core/contacts.md"]
    if intent == "phygital":
        return ["kb/nn/services/phygital.md", "kb/nn/core/contacts.md"]
    if intent == "own_food_rules":
        return ["kb/nn/food/own_food_rules.md", "kb/nn/parties/birthday.md", "kb/nn/core/contacts.md"]
    return ["kb/nn/core/contacts.md"]


def _build_context_chunks_from_files(file_paths: list[str]) -> list[dict]:
    chunks: list[dict] = []
    for fp in file_paths:
        p = Path(fp)
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8").strip()
        if not text:
            continue
        chunks.append({"text": text, "metadata": {"file_path": fp, "heading": None, "chunk_id": "router_fallback"}})
    return chunks


def _primary_file_for_intent(intent: str) -> str | None:
    if intent == "hours":
        return "kb/nn/core/hours.md"
    if intent == "prices":
        return "kb/nn/tickets/prices.md"
    if intent == "discounts":
        return "kb/nn/tickets/discounts.md"
    if intent == "vr":
        return "kb/nn/services/vr.md"
    if intent == "phygital":
        return "kb/nn/services/phygital.md"
    if intent == "own_food_rules":
        return "kb/nn/food/own_food_rules.md"
    return None


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    if not _settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is required for /ask")

    intent = _detect_intent(payload.question)
    if intent != "general":
        context_chunks = build_direct_context(intent)
        if not context_chunks:
            raise HTTPException(status_code=500, detail=f"Direct context for intent='{intent}' is empty")
        answerer = OpenAIAnswerer(_settings)
        result = answerer.generate(SYSTEM_PROMPT_JUICY_V1, context_chunks, payload.question)
        return AskResponse(answer=str(result.get("answer") or ""), sources=list(result.get("sources") or []))

    embedder = OpenAIEmbedder(_settings)
    query_vec = embedder.embed([payload.question])[0]

    store = get_store(_settings, vector_size=len(query_vec))

    top_k = 8
    try:
        hits = store.search(query_vec, top_k)
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        if "dimension" in str(exc).lower():
            detail += " (possible embedding/index dimension mismatch — run: python scripts/reindex_nn.py)"
        raise HTTPException(status_code=500, detail=detail)

    candidates: list[dict] = []
    for h in hits:
        score = float(h.get("score") or 0.0)
        p = h.get("payload") or {}
        text = p.get("text")
        metadata = p.get("metadata")
        if not text or not metadata:
            continue
        file_path = str((metadata or {}).get("file_path") or "")
        candidates.append({"score": score, "text": text, "metadata": metadata, "file_path": file_path})

    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Keep 2–6 chunks by a similarity threshold.
    min_similarity = 0.25
    filtered: list[dict] = []
    if candidates:
        score_levels = sorted({float(c.get("score") or 0.0) for c in candidates}, reverse=True)
        chosen_threshold: float | None = None
        for t in score_levels + [min_similarity]:
            t = max(min_similarity, float(t))
            cnt = sum(1 for c in candidates if float(c.get("score") or 0.0) >= t)
            if 2 <= cnt <= 6:
                chosen_threshold = t
                break
        if chosen_threshold is None:
            # If too many even at min_similarity, just cap later.
            chosen_threshold = min_similarity
        filtered = [c for c in candidates if float(c.get("score") or 0.0) >= chosen_threshold]

    question_words = _tokenize_for_overlap(payload.question)
    primary_file = _primary_file_for_intent(intent)
    for c in filtered:
        chunk_words = _tokenize_for_overlap(str(c.get("text") or ""))
        common = question_words.intersection(chunk_words)
        bonus = 1.0 if (primary_file and c.get("file_path") == primary_file) else 0.0
        c["rerank_score"] = float(len(common)) + 0.1 * float(c.get("score") or 0.0) + bonus
    filtered.sort(key=lambda x: float(x.get("rerank_score") or 0.0), reverse=True)
    filtered = filtered[:6]

    if len(filtered) < 2:
        # Router fallback: use a minimal, topic-focused context instead of random sources.
        fallback_files = _router_fallback_files(intent) if intent != "general" else ["kb/nn/core/contacts.md"]
        context_chunks = _build_context_chunks_from_files(fallback_files)
        if not context_chunks and candidates:
            # As a last resort, include the best retrieved chunk.
            best = candidates[0]
            context_chunks = [{"text": best["text"], "metadata": best["metadata"]}]
        if not context_chunks:
            contacts_text = _read_contacts()
            return AskResponse(answer=_fallback_answer_with_contacts(contacts_text), sources=["kb/nn/core/contacts.md"] if contacts_text else [])
        answerer = OpenAIAnswerer(_settings)
        result = answerer.generate(SYSTEM_PROMPT_JUICY_V1, context_chunks, payload.question)
        return AskResponse(answer=str(result.get("answer") or ""), sources=list(result.get("sources") or []))

    context_chunks = [{"text": c["text"], "metadata": c["metadata"]} for c in filtered[:6]]

    answerer = OpenAIAnswerer(_settings)
    result = answerer.generate(SYSTEM_PROMPT_JUICY_V1, context_chunks, payload.question)
    return AskResponse(answer=str(result.get("answer") or ""), sources=list(result.get("sources") or []))
