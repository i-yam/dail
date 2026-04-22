from __future__ import annotations

"""
services/disinfo_pipeline.py
Message analysis pipeline:
1) retrieval + optional LLM verification against known disinfo database
2) if no DB matches, fallback to classifier model prediction
"""

import asyncio
from dataclasses import dataclass

from services.classifier_gateway import ClassifierPrediction, classify_message
from services.disinfo_matcher import SimilarArticleMatch, find_similar_disinfo_articles
from services.llm_fragment_reviewer import FragmentReviewResult, review_flagged_fragments


@dataclass(frozen=True)
class PipelineResult:
    matches: list[SimilarArticleMatch]
    classifier_prediction: ClassifierPrediction | None
    fragment_review: FragmentReviewResult | None
    decision_source: str  # "db_match" | "classifier_fallback"


async def analyze_message_pipeline(
    message_text: str,
    top_k: int = 3,
    verify_with_llm: bool = True,
    min_score: float = 0.18,
    min_claim_similarity: float = 0.28,
    min_claim_margin: float = 0.23,
) -> PipelineResult:
    matches = await asyncio.to_thread(
        find_similar_disinfo_articles,
        message_text,
        top_k,
        min_score,
        min_claim_similarity,
        min_claim_margin,
        verify_with_llm,
    )
    if matches:
        return PipelineResult(
            matches=matches,
            classifier_prediction=None,
            fragment_review=None,
            decision_source="db_match",
        )

    prediction = await classify_message(message_text)
    fragment_review: FragmentReviewResult | None = None
    if prediction.is_propaganda:
        flagged_fragments = prediction.spans if prediction.spans else [message_text]
        fragment_review = await asyncio.to_thread(
            review_flagged_fragments,
            message_text,
            flagged_fragments,
        )
    return PipelineResult(
        matches=[],
        classifier_prediction=prediction,
        fragment_review=fragment_review,
        decision_source="classifier_fallback",
    )
