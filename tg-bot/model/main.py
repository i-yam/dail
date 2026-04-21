"""
Mock model service. Implements the same /detect contract the real model will.

Purpose: let the bot team (and you) test the full end-to-end UX before
the real detector is ready. The mock uses trivial keyword heuristics so
you can easily trigger all verdict branches:

    "biolab"  | "биолаборатор"      -> match biolabs_ukraine (0.89)
    "NATO"    | "НАТО"              -> match nato_expansion  (0.72 weak)
    "nazi"    | "фашист" | "нацист" -> match ukraine_nazis   (0.85)
    "sanctions" | "санкци"          -> match sanctions_harm  (0.67 weak)
    <20 chars                       -> no_input
    anything else                   -> no_match

The real model will swap this file out — bot doesn't care.

Run:
    uvicorn model.main:app --reload --port 8000
or
    python -m model.main
"""
from __future__ import annotations

import random
from datetime import datetime

from fastapi import FastAPI

from bot.schemas import DetectRequest, DetectResponse, Receipt, Verdict

app = FastAPI(title="narrative-detector (mock)", version="0.1.0")


# ---- canned narratives + receipts -----------------------------------------

_NARRATIVES = {
    "biolabs_ukraine": {
        "label": "US biolabs in Ukraine",
        "explanation": (
            "The message echoes the long-standing pro-Kremlin claim that the "
            "US operates secret biological weapons laboratories in Ukraine. "
            "This narrative has been documented by EUvsDisinfo since 2014 and "
            "surged after Feb 2022."
        ),
        "legal_notes": (
            "FIMI: Fabricated content / False attribution. "
            "DSA: Art. 34(1)(c) — negative effects on civic discourse."
        ),
        "receipts": [
            Receipt(
                date="2022-03-23",
                outlet="RT Arabic",
                title="Pentagon funded biolabs in Ukraine",
                url="https://euvsdisinfo.eu/report/pentagon-funded-biolabs-in-ukraine/",
                similarity=0.91,
            ),
            Receipt(
                date="2023-05-14",
                outlet="Sputnik Poland",
                title="Biolabs produce bio-agents near Russian border",
                url="https://euvsdisinfo.eu/report/biolabs-produce-bio-agents/",
                similarity=0.87,
            ),
            Receipt(
                date="2024-11-09",
                outlet="Tsargrad",
                title="US biological weapons in Kharkiv uncovered",
                url="https://euvsdisinfo.eu/report/us-biological-weapons-kharkiv/",
                similarity=0.82,
            ),
        ],
    },
    "nato_expansion": {
        "label": "NATO provocations and aggressive expansion",
        "explanation": (
            "The message frames NATO as an aggressive, expansionist alliance "
            "provoking Russia — a foundational Kremlin narrative used to "
            "justify military action."
        ),
        "legal_notes": (
            "FIMI: Narrative framing / Historical distortion. "
            "DSA: Art. 34(1)(c) — effects on public discourse."
        ),
        "receipts": [
            Receipt(
                date="2022-02-15",
                outlet="RIA",
                title="NATO encirclement forces Russia to respond",
                url="https://euvsdisinfo.eu/report/nato-encirclement/",
                similarity=0.74,
            ),
            Receipt(
                date="2023-09-03",
                outlet="pl.sputniknews.com",
                title="NATO expansion violates 1990 agreements",
                url="https://euvsdisinfo.eu/report/nato-expansion-1990/",
                similarity=0.70,
            ),
        ],
    },
    "ukraine_nazis": {
        "label": "Ukraine is run by a Nazi regime",
        "explanation": (
            "The message repeats the 'Nazi Ukraine' framing used by the Kremlin "
            "since 2014 to dehumanize Ukrainian statehood and justify military "
            "operations. EUvsDisinfo has documented 400+ instances."
        ),
        "legal_notes": (
            "FIMI: Dehumanization / False historical analogy. "
            "DSA: Art. 34(1)(c). May cross Art. 20 ICCPR (war propaganda)."
        ),
        "receipts": [
            Receipt(
                date="2022-02-28",
                outlet="Pervyi Kanal",
                title="Denazification of Ukraine is a military necessity",
                url="https://euvsdisinfo.eu/report/denazification-ukraine/",
                similarity=0.88,
            ),
            Receipt(
                date="2023-12-20",
                outlet="russian.rt.com",
                title="Zelensky's regime continues Nazi traditions",
                url="https://euvsdisinfo.eu/report/zelensky-nazi-traditions/",
                similarity=0.83,
            ),
            Receipt(
                date="2025-03-15",
                outlet="Tsargrad",
                title="Azov battalion is proof of Ukrainian Nazism",
                url="https://euvsdisinfo.eu/report/azov-ukrainian-nazism/",
                similarity=0.79,
            ),
        ],
    },
    "sanctions_harm": {
        "label": "Sanctions harm the EU more than Russia",
        "explanation": (
            "The message promotes the view that Western sanctions backfire and "
            "primarily damage European economies — a recurring Kremlin talking "
            "point aimed at fracturing EU consensus."
        ),
        "legal_notes": (
            "FIMI: Economic misinformation. "
            "DSA: Art. 34(1)(c) — effects on civic discourse."
        ),
        "receipts": [
            Receipt(
                date="2022-07-11",
                outlet="RIA",
                title="European economy collapsing under own sanctions",
                url="https://euvsdisinfo.eu/report/eu-economy-collapse/",
                similarity=0.69,
            ),
            Receipt(
                date="2024-01-22",
                outlet="Geopolitica.ru",
                title="Sanctions strengthened Russia, weakened EU",
                url="https://euvsdisinfo.eu/report/sanctions-backfire/",
                similarity=0.66,
            ),
        ],
    },
}


# ---- keyword routing ------------------------------------------------------

_RULES: list[tuple[tuple[str, ...], str, float, Verdict]] = [
    (("biolab", "биолаборатор", "biolog"), "biolabs_ukraine", 0.89, Verdict.MATCH),
    (("nazi", "фашист", "нацист", "нациф", "denazif"), "ukraine_nazis", 0.85, Verdict.MATCH),
    (("nato", "нато"), "nato_expansion", 0.72, Verdict.WEAK_MATCH),
    (("sanction", "санкц"), "sanctions_harm", 0.67, Verdict.WEAK_MATCH),
]


def _classify(text: str) -> tuple[Verdict, str | None, float]:
    low = text.lower()
    for keywords, narrative_id, confidence, verdict in _RULES:
        if any(k in low for k in keywords):
            # add small jitter so repeat tests don't look static
            jitter = random.uniform(-0.03, 0.03)
            return verdict, narrative_id, max(0.0, min(1.0, confidence + jitter))
    return Verdict.NO_MATCH, None, 0.0


# ---- endpoints ------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "narrative-detector-mock"}


@app.post("/detect", response_model=DetectResponse)
async def detect(req: DetectRequest) -> DetectResponse:
    text = (req.text or "").strip()
    if len(text) < 20:
        return DetectResponse(
            verdict=Verdict.NO_INPUT,
            error="text_too_short",
        )

    verdict, narrative_id, confidence = _classify(text)

    if verdict == Verdict.NO_MATCH:
        return DetectResponse(
            verdict=Verdict.NO_MATCH,
            confidence=0.0,
            explanation="No documented narrative matched this message.",
        )

    assert narrative_id is not None
    spec = _NARRATIVES[narrative_id]
    return DetectResponse(
        verdict=verdict,
        confidence=confidence,
        narrative_id=narrative_id,
        narrative_label=spec["label"],
        explanation=spec["explanation"],
        receipts=spec["receipts"],
        legal_notes=spec["legal_notes"],
        processed_at=datetime.utcnow(),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("model.main:app", host="0.0.0.0", port=8000, reload=True)