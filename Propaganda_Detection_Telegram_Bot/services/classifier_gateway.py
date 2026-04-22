from __future__ import annotations

"""
services/classifier_gateway.py
Unified gateway for propaganda classification.

Priority:
1) local model in classifier/classifier.py (if available/importable)
2) existing services.classifier backend (API/mock fallback)
"""

import importlib.util
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

logger = logging.getLogger(__name__)

_LOCAL_MODULE: ModuleType | None = None
_LOCAL_MODULE_LOAD_ATTEMPTED = False


@dataclass(frozen=True)
class ClassifierPrediction:
    is_propaganda: bool
    confidence: float
    narrative_label: str
    cluster_id: str | None = None
    spans: list[str] | None = None
    source: str = "unknown"


def _load_local_classifier_module() -> ModuleType | None:
    global _LOCAL_MODULE, _LOCAL_MODULE_LOAD_ATTEMPTED
    if _LOCAL_MODULE_LOAD_ATTEMPTED:
        return _LOCAL_MODULE

    _LOCAL_MODULE_LOAD_ATTEMPTED = True
    module_path = Path(__file__).parent.parent / "classifier" / "classifier.py"
    if not module_path.exists():
        logger.info("Local classifier file not found at %s", module_path)
        return None

    try:
        spec = importlib.util.spec_from_file_location("local_classifier_module", str(module_path))
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        _LOCAL_MODULE = module
        logger.info("Loaded local classifier module from %s", module_path)
        return _LOCAL_MODULE
    except Exception as exc:
        logger.warning("Could not load local classifier module (%s).", exc)
        return None


def _normalize_prediction(result: Any, source: str) -> ClassifierPrediction:
    return ClassifierPrediction(
        is_propaganda=bool(getattr(result, "is_propaganda", False)),
        confidence=float(getattr(result, "confidence", 0.0)),
        narrative_label=str(getattr(result, "narrative_label", "Unknown")),
        cluster_id=getattr(result, "cluster_id", None),
        spans=list(getattr(result, "spans", []) or []),
        source=source,
    )


async def classify_message(text: str) -> ClassifierPrediction:
    """
    Classify message with the best available classifier backend.
    """
    local_module = _load_local_classifier_module()
    if local_module is not None:
        try:
            classify_fn = getattr(local_module, "classify", None)
            if callable(classify_fn):
                result = await classify_fn(text)
                return _normalize_prediction(result, source="local_model")
        except Exception as exc:
            logger.warning("Local classifier inference failed (%s). Falling back.", exc)

    from services.classifier import classify as classify_service  # lazy import

    result = await classify_service(text)
    return _normalize_prediction(result, source="services_classifier")
