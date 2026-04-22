from __future__ import annotations

"""
Standalone CLI tester for services.disinfo_matcher.

Usage examples:
  python3 scripts/test_disinfo_matcher.py --text "EU censors elections..."
  python3 scripts/test_disinfo_matcher.py --interactive
"""

import argparse
import asyncio
import os
from pathlib import Path
import sys

# Make project root importable when script is run directly.
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.disinfo_pipeline import analyze_message_pipeline
from services.llm_verifier import is_llm_verifier_configured


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test semantic matching against known disinformation articles.",
    )
    parser.add_argument(
        "--text",
        type=str,
        default="",
        help="Input text to match against the article base.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="How many top matches to return (default: 3).",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.18,
        help="Minimum disinfo score threshold in [0,1] (default: 0.18).",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Read text interactively from stdin.",
    )
    parser.add_argument(
        "--verify-llm",
        action="store_true",
        help="Run optional LLM verification on top retrieval candidates.",
    )
    parser.add_argument("--csv-path", type=str, default="", help="Override article CSV path for this run.")
    return parser


def _read_interactive_text() -> str:
    print("Paste message text and press Enter:")
    return input("> ").strip()


def _load_local_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    # Ensure .env values are available for CLI tests.
    _load_local_env()

    parser = _build_parser()
    args = parser.parse_args()

    text = args.text.strip()
    if args.interactive:
        text = _read_interactive_text()

    if args.csv_path.strip():
        os.environ["DISINFO_ARTICLES_CSV"] = args.csv_path.strip()

    if not text:
        parser.error("Provide --text or use --interactive.")

    top_k = max(1, min(args.top_k, 20))
    min_score = max(0.0, min(args.min_score, 1.0))

    result = asyncio.run(
        analyze_message_pipeline(
            message_text=text,
            top_k=top_k,
            verify_with_llm=args.verify_llm,
            min_score=min_score,
        )
    )
    matches = result.matches

    print("\nInput:")
    print(text)
    if args.verify_llm:
        if is_llm_verifier_configured():
            print("\nLLM verification: ENABLED")
        else:
            print("\nLLM verification: SKIPPED (check DISINFO_LLM_API_URL / DISINFO_LLM_API_KEY / DISINFO_LLM_MODEL in .env)")
    print("\nMatches:", len(matches))
    if not matches:
        print("No close DB matches found.")
        if result.classifier_prediction is not None:
            pred = result.classifier_prediction
            print("\nClassifier fallback:")
            print(f"   source:         {pred.source}")
            print(f"   is_propaganda:  {pred.is_propaganda}")
            print(f"   confidence:     {pred.confidence:.3f}")
            print(f"   label:          {pred.narrative_label}")
            print(f"   cluster_id:     {pred.cluster_id}")
            print(f"   spans:          {pred.spans or []}")
        if result.fragment_review is not None:
            print("\nLLM fragment review JSON:")
            print(result.fragment_review.raw_json)
        return

    print(f"Engine: {matches[0].engine}")
    print("-" * 80)
    for idx, match in enumerate(matches, 1):
        article = match.article
        print(f"{idx}. score={match.score:.3f}")
        print(f"   claim_similarity:  {match.claim_similarity:.3f}")
        print(f"   debunk_similarity: {match.debunk_similarity:.3f}")
        if match.llm_label is not None:
            print(f"   llm_label:         {match.llm_label}")
            print(f"   llm_confidence:    {(match.llm_confidence or 0.0):.3f}")
            if match.llm_rationale:
                print(f"   llm_rationale:     {match.llm_rationale}")
        print(f"   title: {article.title}")
        print(f"   date:  {article.date_of_publication or 'unknown'}")
        print(f"   url:   {article.report_url}")
        print()


if __name__ == "__main__":
    main()
