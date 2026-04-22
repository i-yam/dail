"""
Model service wired to the project disinformation pipeline.

Run:
    uvicorn model.main:app --reload --port 8000
or
    python -m model.main
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import sys

from fastapi import FastAPI
from dotenv import load_dotenv

from bot.schemas import DetectRequest, DetectResponse, Receipt, Verdict
 
# Make top-level project modules importable (services/, classifier/, etc.).
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load env for model process (uvicorn doesn't auto-load .env).
# Priority: tg-bot/.env first, then project-root .env for shared service keys.
TG_BOT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(TG_BOT_ROOT / ".env")
load_dotenv(ROOT / ".env")

from services.disinfo_pipeline import PipelineResult, analyze_message_pipeline

app = FastAPI(title="narrative-detector (mock)", version="0.1.0")

LEGAL_NOTES_MODEL_STACK = (
    "Classifier model: QCRI/PropagandaTechniquesAnalysis-en-BERT "
    "[[Fine-Grained Analysis of Propaganda in News Articles]"
    "(https://aclanthology.org/D19-1565/) "
    "(Da San Martino et al., EMNLP-IJCNLP 2019)]. "
    "Fragment-level manipulation explanation model: gpt-4o-mini."
)

def _slug(s: str) -> str:
    s = re.sub(r"^DISINFO:\s*", "", s, flags=re.IGNORECASE).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "unknown"


def _shorten(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _is_usable_input(text: str) -> tuple[bool, str]:
    """
    Guardrails against low-signal inputs:
    - too short
    - mostly punctuation / gibberish-like strings
    - tiny standalone questions with no factual claim
    """
    cleaned = (text or "").strip()
    if len(cleaned) < 20:
        return False, "text_too_short"

    tokens = re.findall(r"[A-Za-zА-Яа-я0-9]+", cleaned)
    alpha_tokens = [t for t in tokens if re.search(r"[A-Za-zА-Яа-я]", t)]
    if len(alpha_tokens) < 5:
        return False, "too_few_words"

    # Reject very short, generic questions (no claim to analyze).
    if cleaned.endswith("?") and len(alpha_tokens) < 10:
        return False, "question_too_short"

    # If content is mostly symbols/spaces, treat as noise.
    non_space = [ch for ch in cleaned if not ch.isspace()]
    if non_space:
        symbol_ratio = sum(not ch.isalnum() for ch in non_space) / len(non_space)
        if symbol_ratio > 0.45:
            return False, "mostly_symbols"

    # Low lexical variety in very short inputs often indicates garbage.
    unique_ratio = len(set(t.lower() for t in alpha_tokens)) / max(1, len(alpha_tokens))
    if len(alpha_tokens) < 8 and unique_ratio < 0.45:
        return False, "low_information_text"

    return True, "ok"


def _build_receipts(result: PipelineResult) -> list[Receipt]:
    if not result.matches:
        return []
    receipts: list[Receipt] = []
    for m in result.matches[:3]:
        receipts.append(
            Receipt(
                date=m.article.date_of_publication or "unknown",
                outlet="EUvsDisinfo",
                title=m.article.title,
                url=m.article.report_url,
                similarity=max(0.0, min(1.0, m.score)),
            )
        )
    return receipts


def _build_explanation(result: PipelineResult) -> str:
    if result.matches:
        top = result.matches[0]
        response = (top.article.response or "").strip()
        if response:
            return (
                "Message matches a known disinformation case in the database. "
                "EUvsDisinfo response: " + response
            )
        return "Message matches a known disinformation case in the database."

    pred = result.classifier_prediction
    if pred is None:
        return "No verified database match and classifier fallback unavailable."
    if not pred.is_propaganda:
        return "No verified database match. Classifier marked text as non-propaganda."
    if result.fragment_review and result.fragment_review.fragments:
        return (
            "No verified database match.\n\n"
            "LLM review of propaganda language:\n"
            + "\n".join(
                [
                    (
                        f"{idx}. Technique: {frag.technique}\n"
                        f"   Fragment: \"{_shorten(frag.fragment, 220)}\"\n"
                        f"   Why: {_shorten(frag.explanation, 320)}"
                    )
                    for idx, frag in enumerate(result.fragment_review.fragments[:3], 1)
                ]
            )
        )
    return (
        "No verified database match. Classifier marked propaganda language: "
        f"{pred.narrative_label}."
    )


# ---- endpoints ------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "narrative-detector-mock"}


@app.post("/detect", response_model=DetectResponse)
async def detect(req: DetectRequest) -> DetectResponse:
    text = (req.text or "").strip()
    usable, reason = _is_usable_input(text)
    if not usable:
        return DetectResponse(
            verdict=Verdict.NO_INPUT,
            error=reason,
            explanation=(
                "Input is too short or low-information for reliable propaganda analysis. "
                "Please send a full message or claim."
            ),
        )

    try:
        pipeline = await analyze_message_pipeline(
            message_text=text,
            top_k=3,
            verify_with_llm=True,
        )
    except Exception as exc:
        return DetectResponse(
            verdict=Verdict.ERROR,
            error=f"pipeline_error:{type(exc).__name__}",
        )

    if pipeline.matches:
        top = pipeline.matches[0]
        return DetectResponse(
            verdict=Verdict.MATCH,
            confidence=max(0.0, min(1.0, top.score)),
            narrative_id=f"db_{_slug(top.article.title)}",
            narrative_label=top.article.title,
            explanation=_build_explanation(pipeline),
            receipts=_build_receipts(pipeline),
            legal_notes=(
                "Source: EUvsDisinfo DB match + optional LLM verification. "
                + LEGAL_NOTES_MODEL_STACK
            ),
            processed_at=datetime.utcnow(),
        )

    pred = pipeline.classifier_prediction
    if pred is None:
        return DetectResponse(
            verdict=Verdict.ERROR,
            error="classifier_unavailable",
            explanation=_build_explanation(pipeline),
        )
    if not pred.is_propaganda:
        return DetectResponse(
            verdict=Verdict.NO_MATCH,
            confidence=max(0.0, min(1.0, 1.0 - pred.confidence)),
            explanation=_build_explanation(pipeline),
            legal_notes=LEGAL_NOTES_MODEL_STACK,
            processed_at=datetime.utcnow(),
        )

    return DetectResponse(
        verdict=Verdict.WEAK_MATCH,
        confidence=max(0.0, min(1.0, pred.confidence)),
        narrative_id=f"classifier_{_slug(pred.narrative_label)}",
        narrative_label=pred.narrative_label,
        explanation=_build_explanation(pipeline),
        receipts=[],
        legal_notes=LEGAL_NOTES_MODEL_STACK,
        processed_at=datetime.utcnow(),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("model.main:app", host="0.0.0.0", port=8000, reload=True)