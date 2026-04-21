from __future__ import annotations

"""
services/llm_verifier.py
Optional LLM verification stage for disinfo retrieval candidates.

This module calls an OpenAI-compatible Chat Completions API and asks the model
whether the input message supports a specific disinformation claim.
"""

import json
import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class LLMVerificationResult:
    label: str
    confidence: float
    rationale: str


def _config() -> tuple[str, str, str, float]:
    api_url = os.getenv("DISINFO_LLM_API_URL", "").strip()
    api_key = os.getenv("DISINFO_LLM_API_KEY", "").strip()
    model = os.getenv("DISINFO_LLM_MODEL", "gpt-4o-mini").strip()
    timeout = float(os.getenv("DISINFO_LLM_TIMEOUT", "20"))
    return api_url, api_key, model, timeout


def is_llm_verifier_configured() -> bool:
    api_url, api_key, model, _ = _config()
    return bool(api_url and api_key and model)


def _build_messages(message_text: str, claim_text: str, article_title: str, article_url: str) -> list[dict[str, str]]:
    system_prompt = (
        "You are a strict misinformation-claim verifier.\n"
        "Given an input message and one disinformation claim from a database, classify the relation.\n"
        "Output ONLY valid JSON with keys: label, confidence, rationale.\n"
        "Allowed label values:\n"
        "- supports_claim: message repeats/supports the disinformation claim\n"
        "- refutes_claim: message contradicts/refutes the disinformation claim\n"
        "- different_event_or_neutral: message is about a different event or neutral reporting\n"
        "- uncertain: not enough information\n"
        "confidence must be a float in [0,1]. Keep rationale under 40 words."
    )
    user_prompt = (
        f"Input message:\n{message_text}\n\n"
        f"Disinformation claim:\n{claim_text}\n\n"
        f"Reference title: {article_title}\n"
        f"Reference URL: {article_url}\n\n"
        "Return JSON only."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def verify_message_against_claim(
    message_text: str,
    claim_text: str,
    article_title: str,
    article_url: str,
) -> LLMVerificationResult | None:
    api_url, api_key, model, timeout = _config()
    if not (api_url and api_key and model):
        return None

    payload = {
        "model": model,
        "messages": _build_messages(
            message_text=message_text,
            claim_text=claim_text,
            article_title=article_title,
            article_url=article_url,
        ),
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning("LLM verification request failed (%s).", exc)
        return None

    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        label = str(parsed.get("label", "uncertain"))
        confidence = float(parsed.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
        rationale = str(parsed.get("rationale", "")).strip()
    except Exception as exc:
        logger.warning("LLM verification response parsing failed (%s).", exc)
        return None

    allowed = {"supports_claim", "refutes_claim", "different_event_or_neutral", "uncertain"}
    if label not in allowed:
        label = "uncertain"

    return LLMVerificationResult(
        label=label,
        confidence=confidence,
        rationale=rationale,
    )
