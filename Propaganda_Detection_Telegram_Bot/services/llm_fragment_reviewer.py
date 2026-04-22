from __future__ import annotations

"""
services/llm_fragment_reviewer.py
LLM stage that reviews flagged text fragments and explains manipulation techniques.
"""

import json
import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReviewedFragment:
    fragment: str
    technique: str
    explanation: str


@dataclass(frozen=True)
class FragmentReviewResult:
    disinformation_detected: bool
    fragments: list[ReviewedFragment]
    raw_json: str


def _llm_config() -> tuple[str, str, str, float]:
    api_url = os.getenv("DISINFO_LLM_API_URL", "").strip()
    api_key = os.getenv("DISINFO_LLM_API_KEY", "").strip()
    model = os.getenv("DISINFO_LLM_MODEL", "gpt-4o-mini").strip()
    timeout = float(os.getenv("DISINFO_LLM_TIMEOUT", "20"))
    return api_url, api_key, model, timeout


def _is_configured() -> bool:
    api_url, api_key, model, _ = _llm_config()
    return bool(api_url and api_key and model)


def review_flagged_fragments(
    message_text: str,
    flagged_fragments: list[str],
) -> FragmentReviewResult | None:
    if not _is_configured():
        return None

    api_url, api_key, model, timeout = _llm_config()
    unique_fragments = [frag.strip() for frag in flagged_fragments if frag and frag.strip()]
    if not unique_fragments:
        return None

    system_prompt = (
        "You are a propaganda and disinformation detection expert.\n\n"
        "You will receive a news message or Telegram post in English, along with fragments that have been flagged by a detection model.\n\n"
        "Your job is to:\n"
        "1. Review each flagged fragment\n"
        "2. Explain clearly why it is propaganda or disinformation\n"
        "3. Identify which propaganda technique is being used\n\n"
        "Use only these propaganda techniques:\n"
        "- Exaggeration\n"
        "- Manipulation\n"
        "- Loaded Language\n"
        "- Appeal to Fear\n"
        "- Whataboutism\n"
        "- Repetition\n"
        "- Black-and-White Fallacy\n"
        "- Appeal to Authority\n"
        "- Taken Out of Context\n\n"
        "Always respond in this exact JSON format:\n\n"
        "{\n"
        '  "disinformation_detected": true or false,\n'
        '  "fragments": [\n'
        "    {\n"
        '      "fragment": "exact quote from the original text",\n'
        '      "technique": "name of the propaganda technique",\n'
        '      "explanation": "why this is propaganda or disinformation"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Always quote the EXACT fragment from the original text\n"
        '- Be specific in your explanation — do not just say "this is false"\n'
        "- Do not flag opinions or satire unless clearly manipulative\n"
        "- If no disinformation is found, return disinformation_detected as false and empty fragments array"
    )
    user_prompt = (
        f"Original text:\n{message_text}\n\n"
        f"Flagged fragments from detection model:\n{json.dumps(unique_fragments, ensure_ascii=False)}\n\n"
        "Return JSON only."
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
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
            raw_content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("LLM fragment review request failed (%s).", exc)
        return None

    try:
        parsed = json.loads(raw_content)
        detected = bool(parsed.get("disinformation_detected", False))
        fragments_raw = parsed.get("fragments", [])
        fragments: list[ReviewedFragment] = []
        allowed = {"Exaggeration", "False Context", "False Information", "Taken Out of Context"}
        for item in fragments_raw:
            fragment = str(item.get("fragment", "")).strip()
            technique = str(item.get("technique", "")).strip()
            explanation = str(item.get("explanation", "")).strip()
            if not fragment:
                continue
            if technique not in allowed:
                technique = "False Context"
            fragments.append(
                ReviewedFragment(
                    fragment=fragment,
                    technique=technique,
                    explanation=explanation,
                )
            )
        return FragmentReviewResult(
            disinformation_detected=detected,
            fragments=fragments,
            raw_json=raw_content,
        )
    except Exception as exc:
        logger.warning("LLM fragment review parsing failed (%s).", exc)
        return None
