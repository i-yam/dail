from __future__ import annotations
"""
services/classifier.py
HTTP client that calls the teammates' propaganda classification API.

Expected API contract:
    POST {CLASSIFIER_API_URL}/classify
    Body:  { "text": "<message content>" }
    Response:
    {
        "is_propaganda": true,
        "confidence": 0.92,
        "narrative_label": "Anti-NATO destabilisation",
        "cluster_id": "cluster_42"        # optional
    }

If CLASSIFIER_API_URL is not set or the API is unreachable,
the module falls back to a local MOCK classifier (keyword heuristics)
so the bot can be demoed independently.
"""

import os
import logging
import random
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

CLASSIFIER_API_URL: str | None = os.getenv("CLASSIFIER_API_URL")  # e.g. http://localhost:8001
CLASSIFIER_TIMEOUT: float = float(os.getenv("CLASSIFIER_TIMEOUT", "10"))


@dataclass
class ClassificationResult:
    is_propaganda: bool
    confidence: float
    narrative_label: str
    cluster_id: str | None = field(default=None)

    def __str__(self) -> str:
        flag = "🚨 PROPAGANDA" if self.is_propaganda else "✅ CLEAN"
        return (
            f"{flag}  [{self.confidence:.0%}]\n"
            f"Narrative: {self.narrative_label}\n"
            f"Cluster:   {self.cluster_id or 'unassigned'}"
        )


# ── Real API client ───────────────────────────────────────────────────────────

async def classify(text: str) -> ClassificationResult:
    """
    Send `text` to the classifier API and return a ClassificationResult.
    Falls back to mock if the API URL is absent or unreachable.
    """
    if not CLASSIFIER_API_URL:
        logger.warning("CLASSIFIER_API_URL not set — using mock classifier.")
        return _mock_classify(text)

    endpoint = f"{CLASSIFIER_API_URL.rstrip('/')}/classify"
    try:
        async with httpx.AsyncClient(timeout=CLASSIFIER_TIMEOUT) as client:
            response = await client.post(endpoint, json={"text": text})
            response.raise_for_status()
            data = response.json()

        return ClassificationResult(
            is_propaganda=bool(data.get("is_propaganda", False)),
            confidence=float(data.get("confidence", 0.0)),
            narrative_label=str(data.get("narrative_label", "Unknown")),
            cluster_id=data.get("cluster_id"),
        )

    except httpx.HTTPStatusError as exc:
        logger.error("Classifier API returned %s — falling back to mock.", exc.response.status_code)
        return _mock_classify(text)
    except Exception as exc:
        logger.error("Classifier API unreachable (%s) — falling back to mock.", exc)
        return _mock_classify(text)


# ── Mock classifier (keyword heuristics) ─────────────────────────────────────
# Used during dev / demo when the real model isn't ready yet.

_PROPAGANDA_SIGNALS: list[tuple[str, str, str]] = [
    # (keyword_fragment, narrative_label, cluster_id)
    ("nato", "Anti-NATO destabilisation",       "cluster_nato"),
    ("biolabs", "Biolabs conspiracy",            "cluster_biolabs"),
    ("deep state", "Deep-state narrative",       "cluster_deep_state"),
    ("zelensky", "Zelensky delegitimisation",    "cluster_zelensky"),
    ("false flag", "False-flag accusation",      "cluster_false_flag"),
    ("genocide", "Genocide framing",             "cluster_genocide"),
    ("sanctions", "Sanctions-backfire narrative","cluster_sanctions"),
    ("nazi", "Neo-Nazi labelling",               "cluster_nazi"),
    ("special operation", "War-euphemism framing","cluster_special_op"),
    ("bioweapon", "Bioweapon conspiracy",        "cluster_biolabs"),
    ("ukraine is losing", "Defeatism narrative", "cluster_defeatism"),
    ("western media lies", "MSM distrust frame", "cluster_msm"),
]


def _mock_classify(text: str) -> ClassificationResult:
    """
    Heuristic mock: scan for known propaganda keywords.
    Returns a realistic-looking result for demo purposes.
    """
    lower = text.lower()
    for keyword, label, cluster_id in _PROPAGANDA_SIGNALS:
        if keyword in lower:
            confidence = round(random.uniform(0.75, 0.97), 2)
            return ClassificationResult(
                is_propaganda=True,
                confidence=confidence,
                narrative_label=label,
                cluster_id=cluster_id,
            )

    # Not propaganda
    confidence = round(random.uniform(0.78, 0.99), 2)
    return ClassificationResult(
        is_propaganda=False,
        confidence=confidence,
        narrative_label="None detected",
        cluster_id=None,
    )
