"""HTTP client for the model service. One connection pool, typed in/out."""
from __future__ import annotations

import logging

import httpx

from .schemas import DetectRequest, DetectResponse, Verdict

log = logging.getLogger(__name__)


class ModelClient:
    def __init__(self, base_url: str, timeout_s: float = 20.0):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_s,
            headers={"Content-Type": "application/json"},
        )

    async def detect(self, req: DetectRequest) -> DetectResponse:
        """Call POST /detect. On network/parse errors, return an error-verdict."""
        try:
            resp = await self._client.post(
                "/detect", json=req.model_dump(exclude_none=False)
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            log.warning("model returned %s: %s", e.response.status_code, e.response.text[:200])
            return DetectResponse(
                verdict=Verdict.ERROR,
                error=f"http_{e.response.status_code}",
            )
        except httpx.RequestError as e:
            log.warning("model unreachable: %s", e)
            return DetectResponse(
                verdict=Verdict.ERROR,
                error="model_unreachable",
            )

        try:
            return DetectResponse.model_validate(resp.json())
        except Exception as e:
            log.warning("bad response shape: %s", e)
            return DetectResponse(verdict=Verdict.ERROR, error="bad_response")

    async def health(self) -> bool:
        try:
            r = await self._client.get("/health", timeout=3)
            return r.status_code == 200
        except httpx.RequestError:
            return False

    async def close(self) -> None:
        await self._client.aclose()
