from __future__ import annotations

"""
services/disinfo_matcher.py
Find semantically similar EUvsDisinfo articles for an input message.

Design goals:
- clean API for Telegram integration (`find_similar_disinfo_articles`)
- semantic matching when sentence-transformers is available
- no hard dependency on ML libs (safe lexical fallback)
"""

import csv
import logging
import math
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_ARTICLES_CSV = Path(__file__).parent.parent / "data" / "processed" / "euvsdisinfo_reports.csv"
EMBEDDING_MODEL_NAME = os.getenv("DISINFO_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "have", "has", "been", "into",
    "about", "their", "they", "them", "what", "when", "were", "will", "would", "could",
    "should", "more", "than", "only", "some", "such", "also", "very", "over", "under",
    "after", "before", "most", "much", "many", "because", "while", "where", "which",
    "against", "through", "between", "using", "used", "been", "being", "is", "are",
    "was", "to", "of", "in", "on", "as", "it", "its", "a", "an", "or", "by", "at",
}
DISINFO_CUE_PATTERNS = [
    r"\bcensorship\b",
    r"\bpropaganda\b",
    r"\bregime\b",
    r"\bnazi\b",
    r"\bfalse\s*flag\b",
    r"\bdeep\s*state\b",
    r"\bcolour\s*revolution\b",
    r"\bplot\b",
    r"\bconspiracy\b",
    r"\bmanipulat\w*\b",
    r"\bsuppress\w*\b",
    r"\bpuppet\w*\b",
    r"\bfake\b",
    r"\bstaged?\b",
]


@dataclass(frozen=True)
class DisinfoArticle:
    report_url: str
    title: str
    summary: str
    response: str
    tags: str
    date_of_publication: str


@dataclass(frozen=True)
class SimilarArticleMatch:
    article: DisinfoArticle
    score: float  # calibrated confidence-like score in [0, 1]
    claim_similarity: float
    debunk_similarity: float
    engine: str   # "embedding" or "lexical"
    llm_label: str | None = None
    llm_confidence: float | None = None
    llm_rationale: str | None = None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _strip_disinfo_prefix(text: str) -> str:
    return re.sub(r"^\s*disinfo:\s*", "", text or "", flags=re.IGNORECASE).strip()


def _tokenize(text: str) -> list[str]:
    # Keep alpha-numeric words and collapse punctuation/noise.
    return re.findall(r"[a-z0-9]{2,}", text.lower())


def _cosine_sparse(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    for key, value in a.items():
        dot += value * b.get(key, 0.0)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _build_claim_for_llm(article: DisinfoArticle) -> str:
    title = _strip_disinfo_prefix(article.title)
    return " ".join(part for part in [title, article.summary] if part).strip()


def _resolve_articles_csv_path() -> Path:
    configured = os.getenv("DISINFO_ARTICLES_CSV", "").strip()
    if configured:
        return Path(configured)
    return DEFAULT_ARTICLES_CSV


class DisinfoMatcher:
    """
    Loads known disinfo articles and returns top similar records for a message.
    """

    def __init__(self, csv_path: Path | None = None) -> None:
        self.csv_path = csv_path or _resolve_articles_csv_path()
        self.articles: list[DisinfoArticle] = []
        self.claim_texts: list[str] = []
        self.debunk_texts: list[str] = []
        self._title_keyword_sets: list[set[str]] = []

        self._idf_claim: dict[str, float] = {}
        self._idf_debunk: dict[str, float] = {}
        self._claim_vectors: list[dict[str, float]] = []
        self._debunk_vectors: list[dict[str, float]] = []

        # Optional embedding index.
        self._embedding_model = None
        self._claim_embeddings = None
        self._debunk_embeddings = None
        self._engine = "lexical"
        self._ready = False

    def _build_claim_text(self, row: dict[str, str]) -> str:
        title = row.get("title", "")
        title = re.sub(r"^\s*disinfo:\s*", "", title, flags=re.IGNORECASE)
        return " ".join(
            filter(
                None,
                [
                    title,
                    row.get("summary", ""),
                    row.get("tags", ""),
                ],
            )
        ).strip()

    def _build_debunk_text(self, row: dict[str, str]) -> str:
        return " ".join(
            filter(
                None,
                [
                    row.get("response", ""),
                ],
            )
        ).strip()

    def _load_articles(self) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Disinfo CSV not found: {self.csv_path}")

        with self.csv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            required_columns = {"title", "summary", "response", "report_url"}
            available_columns = set(reader.fieldnames or [])
            if not required_columns.issubset(available_columns):
                missing = sorted(required_columns - available_columns)
                raise RuntimeError(
                    f"CSV schema is incompatible for matcher: missing columns {missing}. "
                    "Expected an enriched reports CSV with title/summary/response/report_url."
                )
            for row in reader:
                article = DisinfoArticle(
                    report_url=row.get("report_url", ""),
                    title=row.get("title", ""),
                    summary=row.get("summary", ""),
                    response=row.get("response", ""),
                    tags=row.get("tags", ""),
                    date_of_publication=row.get("date_of_publication", ""),
                )
                claim_text = self._build_claim_text(row)
                debunk_text = self._build_debunk_text(row)
                if not claim_text:
                    continue
                self.articles.append(article)
                self.claim_texts.append(_normalize(claim_text))
                self.debunk_texts.append(_normalize(debunk_text))
                self._title_keyword_sets.append(self._keywords(article.title))

        if not self.articles:
            raise RuntimeError("No articles loaded from disinfo CSV.")

    def _build_lexical_index_for(self, texts: list[str]) -> tuple[dict[str, float], list[dict[str, float]]]:
        # Simple TF-IDF index in pure Python (portable fallback).
        doc_tokens: list[list[str]] = [_tokenize(text) for text in texts]
        df: dict[str, int] = {}
        for tokens in doc_tokens:
            for term in set(tokens):
                df[term] = df.get(term, 0) + 1

        n_docs = len(doc_tokens)
        idf = {
            term: math.log((1 + n_docs) / (1 + freq)) + 1.0
            for term, freq in df.items()
        }

        vectors: list[dict[str, float]] = []
        for tokens in doc_tokens:
            tf: dict[str, float] = {}
            for term in tokens:
                tf[term] = tf.get(term, 0.0) + 1.0
            if tf:
                inv_total = 1.0 / len(tokens)
                for term in list(tf.keys()):
                    tf[term] = (tf[term] * inv_total) * idf.get(term, 1.0)
            vectors.append(tf)
        return idf, vectors

    def _build_lexical_index(self) -> None:
        self._idf_claim, self._claim_vectors = self._build_lexical_index_for(self.claim_texts)
        self._idf_debunk, self._debunk_vectors = self._build_lexical_index_for(self.debunk_texts)

    def _try_build_embedding_index(self) -> bool:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception:
            return False

        try:
            model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            claim_embeddings = model.encode(
                self.claim_texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            debunk_embeddings = model.encode(
                self.debunk_texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            self._embedding_model = model
            self._claim_embeddings = claim_embeddings
            self._debunk_embeddings = debunk_embeddings
            return True
        except Exception as exc:
            logger.warning("Embedding index unavailable (%s). Falling back to lexical index.", exc)
            return False

    def _ensure_ready(self) -> None:
        if self._ready:
            return

        self._load_articles()
        self._build_lexical_index()

        if self._try_build_embedding_index():
            self._engine = "embedding"
            logger.info("DisinfoMatcher ready with embedding engine.")
        else:
            self._engine = "lexical"
            logger.info("DisinfoMatcher ready with lexical engine.")

        self._ready = True

    def _vectorize_query(self, text: str, idf: dict[str, float]) -> dict[str, float]:
        tokens = _tokenize(_normalize(text))
        tf: dict[str, float] = {}
        for term in tokens:
            tf[term] = tf.get(term, 0.0) + 1.0
        if tf:
            inv_total = 1.0 / len(tokens)
            for term in list(tf.keys()):
                tf[term] = (tf[term] * inv_total) * idf.get(term, 1.0)
        return tf

    def _score_with_embeddings(self, text: str) -> tuple[list[float], list[float]]:
        if self._embedding_model is None or self._claim_embeddings is None or self._debunk_embeddings is None:
            return [], []
        query_embedding = self._embedding_model.encode(
            [text],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        # Row-wise dot products; embeddings are L2-normalized.
        claim_scores = [float(row.dot(query_embedding)) for row in self._claim_embeddings]
        debunk_scores = [float(row.dot(query_embedding)) for row in self._debunk_embeddings]
        return claim_scores, debunk_scores

    def _score_lexical(self, text: str) -> tuple[list[float], list[float]]:
        claim_query = self._vectorize_query(text, self._idf_claim)
        debunk_query = self._vectorize_query(text, self._idf_debunk)
        claim_scores = [_cosine_sparse(claim_query, article_vec) for article_vec in self._claim_vectors]
        debunk_scores = [_cosine_sparse(debunk_query, article_vec) for article_vec in self._debunk_vectors]
        return claim_scores, debunk_scores

    @staticmethod
    def _disinfo_score(claim_similarity: float, debunk_similarity: float) -> float:
        # Higher only when text is closer to the disinfo claim than to the debunk.
        return max(0.0, claim_similarity - debunk_similarity)

    @staticmethod
    def _calibrated_score(claim_similarity: float, debunk_similarity: float, anchor_overlap_ratio: float) -> float:
        """
        Human-facing score:
        - keeps exact/near-exact claim matches high
        - rewards positive claim-vs-debunk margin
        - lightly boosts strong anchor overlap
        """
        margin = max(0.0, claim_similarity - debunk_similarity)
        score = (0.80 * claim_similarity) + (0.20 * margin) + (0.10 * anchor_overlap_ratio)
        return min(1.0, max(0.0, score))

    @staticmethod
    def _query_disinfo_cue_strength(query: str) -> float:
        # Down-weight broad neutral war reporting, which often lacks disinfo framing cues.
        if not query:
            return 0.0
        hits = sum(1 for pattern in DISINFO_CUE_PATTERNS if re.search(pattern, query))
        return min(1.0, hits / 4.0)

    @staticmethod
    def _keywords(text: str) -> set[str]:
        return {
            token for token in _tokenize(_normalize(text))
            if token not in STOPWORDS and len(token) >= 4
        }

    def match(
        self,
        message_text: str,
        top_k: int = 3,
        min_score: float = 0.18,
        min_claim_similarity: float = 0.28,
        min_claim_margin: float = 0.23,
    ) -> list[SimilarArticleMatch]:
        self._ensure_ready()

        query = _normalize(message_text)
        if not query:
            return []

        if self._engine == "embedding":
            claim_scores, debunk_scores = self._score_with_embeddings(query)
        else:
            claim_scores, debunk_scores = self._score_lexical(query)

        combined_scores = [
            self._disinfo_score(claim_similarity=claim, debunk_similarity=debunk)
            for claim, debunk in zip(claim_scores, debunk_scores)
        ]
        query_cue_strength = self._query_disinfo_cue_strength(query)
        cue_weight = 0.60 + (0.40 * query_cue_strength)
        query_keywords = self._keywords(query)
        adjusted_scores: list[float] = []
        overlap_ratios: list[float] = []
        for idx, score in enumerate(combined_scores):
            title_keywords = self._title_keyword_sets[idx]
            if title_keywords:
                title_weight_total = sum(self._idf_claim.get(token, 1.0) for token in title_keywords)
                title_weight_matched = sum(
                    self._idf_claim.get(token, 1.0)
                    for token in (query_keywords & title_keywords)
                )
                overlap_ratio = (title_weight_matched / title_weight_total) if title_weight_total else 0.0
            else:
                overlap_ratio = 0.0
            # Boost exact narrative anchors (e.g. Orban/Tisza/Druzhba) while keeping semantic core.
            anchor_boost = 0.12 * overlap_ratio
            adjusted_scores.append((score * cue_weight) + anchor_boost)
            overlap_ratios.append(overlap_ratio)
        combined_scores = adjusted_scores
        ranked = sorted(
            enumerate(combined_scores),
            key=lambda item: item[1],
            reverse=True,
        )

        hits: list[SimilarArticleMatch] = []
        for idx, score in ranked[: max(top_k * 5, top_k)]:
            claim_similarity = claim_scores[idx]
            debunk_similarity = debunk_scores[idx]
            claim_margin = claim_similarity - debunk_similarity
            # Partial quotes of exact disinfo claims can have high claim similarity
            # but reduced margin because they contain fewer unique anchors.
            effective_min_claim_margin = min_claim_margin
            if claim_similarity >= 0.85:
                effective_min_claim_margin = min(effective_min_claim_margin, 0.12)
            elif claim_similarity >= 0.75:
                effective_min_claim_margin = min(effective_min_claim_margin, 0.16)
            if (
                claim_similarity < min_claim_similarity
                or claim_margin < effective_min_claim_margin
                or score < min_score
            ):
                continue
            hits.append(
                SimilarArticleMatch(
                    article=self.articles[idx],
                    score=self._calibrated_score(
                        claim_similarity=claim_similarity,
                        debunk_similarity=debunk_similarity,
                        anchor_overlap_ratio=overlap_ratios[idx],
                    ),
                    claim_similarity=claim_similarity,
                    debunk_similarity=debunk_similarity,
                    engine=self._engine,
                )
            )
            if len(hits) >= top_k:
                break
        return hits


_MATCHER_SINGLETON: DisinfoMatcher | None = None


def get_disinfo_matcher() -> DisinfoMatcher:
    global _MATCHER_SINGLETON
    if _MATCHER_SINGLETON is None:
        _MATCHER_SINGLETON = DisinfoMatcher()
    return _MATCHER_SINGLETON


def find_similar_disinfo_articles(
    message_text: str,
    top_k: int = 3,
    min_score: float = 0.18,
    min_claim_similarity: float = 0.28,
    min_claim_margin: float = 0.23,
    verify_with_llm: bool = False,
    llm_max_candidates: int = 3,
    llm_min_confidence: float = 0.55,
) -> list[SimilarArticleMatch]:
    """
    Convenience function for handlers/services.
    """
    matcher = get_disinfo_matcher()
    matches = matcher.match(
        message_text=message_text,
        top_k=top_k,
        min_score=min_score,
        min_claim_similarity=min_claim_similarity,
        min_claim_margin=min_claim_margin,
    )
    if not verify_with_llm or not matches:
        return matches

    try:
        from services.llm_verifier import (
            is_llm_verifier_configured,
            verify_message_against_claim,
        )
    except Exception as exc:
        logger.warning("LLM verifier import failed (%s). Returning retrieval-only matches.", exc)
        return matches

    if not is_llm_verifier_configured():
        return matches

    verified: list[SimilarArticleMatch] = []
    candidates = matches[: max(1, min(llm_max_candidates, len(matches)))]
    for match in candidates:
        claim_text = _build_claim_for_llm(match.article)
        result = verify_message_against_claim(
            message_text=message_text,
            claim_text=claim_text,
            article_title=match.article.title,
            article_url=match.article.report_url,
        )
        if result is None:
            continue
        enriched = replace(
            match,
            llm_label=result.label,
            llm_confidence=result.confidence,
            llm_rationale=result.rationale,
        )
        if result.label == "supports_claim" and result.confidence >= llm_min_confidence:
            verified.append(enriched)

    return verified
