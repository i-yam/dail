from __future__ import annotations
"""
services/classifier.py
Propaganda classifier using the QCRI joint BERT model.

Model: QCRI/PropagandaTechniquesAnalysis-en-BERT
  - Trained on SemEval-2020 Task 11 (18 propaganda techniques)
  - Jointly classifies at SEQUENCE level (is this propaganda + which technique?)
    and TOKEN level (which exact words are the propaganda spans?)
  - Paper: https://arxiv.org/abs/2009.02624

Architecture: BertForTokenAndSequenceJointClassification
  - Sequence head → multi-label F1 per technique (document level)
  - Token head   → BIO tagging of propaganda spans (word level)

Fallback: if the QCRI custom class fails to load, we fall back to
zero-shot classification with facebook/bart-large-mnli.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field

import torch

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

QCRI_MODEL = "QCRI/PropagandaTechniquesAnalysis-en-BERT"
FALLBACK_MODEL = os.getenv("HF_FALLBACK_MODEL", "cross-encoder/nli-deberta-v3-small")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.35"))

# Technique → cluster id mapping (aligns with SemEval-2020 propaganda labels)
_TECHNIQUE_TO_CLUSTER: dict[str, str] = {
    "appeal to authority":              "cluster_authority",
    "appeal to fear/prejudice":         "cluster_fear",
    "appeal to fear-prejudice":         "cluster_fear",
    "bandwagon":                        "cluster_bandwagon",
    "black-and-white fallacy":          "cluster_false_dichotomy",
    "causal oversimplification":        "cluster_oversimplification",
    "doubt":                            "cluster_doubt",
    "exaggeration/minimisation":        "cluster_exaggeration",
    "exaggeration,minimisation":        "cluster_exaggeration",
    "flag-waving":                      "cluster_flag_waving",
    "loaded language":                  "cluster_loaded_language",
    "name calling/labeling":            "cluster_name_calling",
    "name calling,labeling":            "cluster_name_calling",
    "repetition":                       "cluster_repetition",
    "slogans":                          "cluster_slogans",
    "thought-terminating clichés":      "cluster_cliches",
    "whataboutism":                     "cluster_whataboutism",
    "red herring":                      "cluster_red_herring",
    "straw man":                        "cluster_straw_man",
}


def _label_to_cluster(label: str) -> str | None:
    return _TECHNIQUE_TO_CLUSTER.get(label.lower().strip(), f"cluster_{label[:20].lower().replace(' ', '_')}")


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    is_propaganda: bool
    confidence: float
    narrative_label: str
    cluster_id: str | None = field(default=None)
    spans: list[str] = field(default_factory=list)  # exact propagandistic words/phrases

    def __str__(self) -> str:
        flag = "🚨 PROPAGANDA" if self.is_propaganda else "✅ CLEAN"
        span_str = f"\nSpans: {' | '.join(self.spans)}" if self.spans else ""
        return (
            f"{flag}  [{self.confidence:.0%}]\n"
            f"Technique : {self.narrative_label}\n"
            f"Cluster   : {self.cluster_id or 'none'}"
            f"{span_str}"
        )


# ── Model singletons ──────────────────────────────────────────────────────────

_tokenizer = None
_model = None
_mode = None          # "qcri" | "fallback_pipeline"
_fallback_pipe = None


def _load_qcri() -> bool:
    """
    Attempt to load the QCRI joint BERT model.
    Returns True if successful, False if we should fall back.
    """
    global _tokenizer, _model, _mode

    try:
        from transformers import (
            AutoTokenizer,
            BertForTokenAndSequenceJointClassification,
        )

        logger.info("Loading QCRI propaganda model: %s", QCRI_MODEL)
        _tokenizer = AutoTokenizer.from_pretrained(QCRI_MODEL)
        _model = BertForTokenAndSequenceJointClassification.from_pretrained(QCRI_MODEL)
        _model.eval()
        _mode = "qcri"
        logger.info("✅ QCRI model loaded successfully.")
        return True

    except Exception as exc:
        logger.warning(
            "QCRI model failed to load (%s). Falling back to zero-shot classifier.", exc
        )
        return False


def _load_fallback() -> None:
    """Load the zero-shot fallback pipeline."""
    global _fallback_pipe, _mode

    from transformers import pipeline as hf_pipeline  # noqa: PLC0415

    logger.info("Loading fallback zero-shot model: %s", FALLBACK_MODEL)
    _fallback_pipe = hf_pipeline(
        "zero-shot-classification",
        model=FALLBACK_MODEL,
        device=-1,
    )
    _mode = "fallback_pipeline"
    logger.info("✅ Fallback model loaded.")


def warmup() -> None:
    """Pre-load whichever model is available at startup."""
    if not _load_qcri():
        _load_fallback()


# ── Inference ─────────────────────────────────────────────────────────────────

async def classify(text: str) -> ClassificationResult:
    """
    Classify `text` for propaganda. Runs in a thread pool to keep the bot async.
    """
    # Ensure model is loaded
    if _mode is None:
        warmup()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _classify_sync, text)


def _classify_sync(text: str) -> ClassificationResult:
    """Synchronous classification — called inside run_in_executor."""
    if _mode == "qcri":
        return _classify_qcri(text)
    return _classify_fallback(text)


# ── QCRI inference ────────────────────────────────────────────────────────────

def _classify_qcri(text: str) -> ClassificationResult:
    inputs = _tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        return_offsets_mapping=True,
    )

    offset_mapping = inputs.pop("offset_mapping")   # not a model input

    with torch.no_grad():
        outputs = _model(**inputs)

    # ── Sequence head: which technique? ──────────────────────────────────────
    # The joint model uses sigmoid for multi-label sequence classification
    if hasattr(outputs, "sequence_logits"):
        seq_logits = outputs.sequence_logits
    elif hasattr(outputs, "logits"):
        seq_logits = outputs.logits
    else:
        seq_logits = list(outputs)[0]

    seq_probs = torch.sigmoid(seq_logits)[0]          # shape: [num_labels]
    top_idx = int(seq_probs.argmax().item())
    top_score = float(seq_probs[top_idx].item())

    id2label = _model.config.id2label
    top_label = id2label.get(top_idx, f"Technique_{top_idx}")

    is_propaganda = top_score >= CONFIDENCE_THRESHOLD

    # ── Token head: extract propaganda spans ──────────────────────────────────
    spans: list[str] = []
    if is_propaganda and hasattr(outputs, "token_logits"):
        spans = _extract_spans(
            text=text,
            token_logits=outputs.token_logits,
            input_ids=inputs["input_ids"],
            offset_mapping=offset_mapping,
        )

    return ClassificationResult(
        is_propaganda=is_propaganda,
        confidence=top_score,
        narrative_label=top_label if is_propaganda else "None detected",
        cluster_id=_label_to_cluster(top_label) if is_propaganda else None,
        spans=spans,
    )


def _extract_spans(
    text: str,
    token_logits: torch.Tensor,
    input_ids: torch.Tensor,
    offset_mapping: torch.Tensor,
) -> list[str]:
    """
    Decode BIO token labels back to character spans in the original text.
    Returns a list of unique propaganda span strings.
    """
    try:
        # token_logits: [batch, seq_len, num_token_labels]
        token_preds = token_logits[0].argmax(dim=-1).tolist()   # [seq_len]
        offsets = offset_mapping[0].tolist()                     # [seq_len, 2]

        spans: list[str] = []
        current_start: int | None = None
        current_end: int = 0

        for pred, (start, end) in zip(token_preds, offsets):
            if start == end:          # special token (CLS/SEP/PAD)
                if current_start is not None:
                    span_text = text[current_start:current_end].strip()
                    if span_text:
                        spans.append(span_text)
                    current_start = None
                continue

            is_propaganda_token = pred != 0   # 0 = O (outside)

            if is_propaganda_token:
                if current_start is None:
                    current_start = start
                current_end = end
            else:
                if current_start is not None:
                    span_text = text[current_start:current_end].strip()
                    if span_text:
                        spans.append(span_text)
                    current_start = None

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_spans: list[str] = []
        for s in spans:
            if s not in seen:
                seen.add(s)
                unique_spans.append(s)

        return unique_spans[:5]   # cap at 5 spans per message

    except Exception as exc:
        logger.debug("Span extraction failed (non-critical): %s", exc)
        return []


# ── Fallback zero-shot inference ──────────────────────────────────────────────

_FALLBACK_LABELS = [
    "Anti-NATO destabilisation narrative",
    "Biolabs or bioweapon conspiracy",
    "False flag accusation",
    "Genocide or war crimes denial",
    "War euphemism or whitewashing aggression",
    "Deep state or shadow government narrative",
    "Western media distrust and disinformation",
    "Zelensky delegitimisation narrative",
    "Loaded language and name calling",
    "Appeal to fear or prejudice",
    "Neutral factual reporting",       # ← clean label, must be last
]
_FALLBACK_CLEAN = _FALLBACK_LABELS[-1]


def _classify_fallback(text: str) -> ClassificationResult:
    raw = _fallback_pipe(text, candidate_labels=_FALLBACK_LABELS, multi_label=False)
    top_label: str = raw["labels"][0]
    top_score: float = raw["scores"][0]
    is_propaganda = (top_label != _FALLBACK_CLEAN) and (top_score >= CONFIDENCE_THRESHOLD)

    return ClassificationResult(
        is_propaganda=is_propaganda,
        confidence=top_score,
        narrative_label=top_label if is_propaganda else "None detected",
        cluster_id=_label_to_cluster(top_label) if is_propaganda else None,
        spans=[],   # fallback model doesn't do token spans
    )
