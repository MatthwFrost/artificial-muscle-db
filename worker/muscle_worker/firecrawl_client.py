"""Firecrawl API wrapper. Handles scrape (v2) and agent (v2) calls.

The `/agent` endpoint (launched Feb 2026, successor to `/extract`) fetches the target
URL(s) itself and returns structured JSON matching a provided schema. Spark models
(`spark-1-fast` | `spark-1-mini` | `spark-1-pro`) are selected via the top-level `model`
field on `/agent`."""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import CONFIG


class FirecrawlClient:
    def __init__(self, api_key: str | None = None, api_url: str | None = None, timeout: float = 300.0):
        self.api_key = api_key or CONFIG.firecrawl_api_key
        self.api_url = (api_url or CONFIG.firecrawl_api_url).rstrip("/")
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError("FIRECRAWL_API_KEY not set")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=30))
    def scrape(self, url: str, formats: tuple[str, ...] = ("markdown",)) -> dict:
        """Fetch a URL and return its content in the requested formats."""
        payload = {"url": url, "formats": list(formats)}
        resp = httpx.post(
            f"{self.api_url}/v2/scrape",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=60))
    def agent(
        self,
        prompt: str,
        schema: dict,
        urls: list[str] | None = None,
        model: str | None = None,
        max_credits: int | None = None,
    ) -> dict:
        """Run an /agent extraction. Spark-1-pro by default.

        `schema` is a JSON-schema dict (from a Pydantic model via `.model_json_schema()`).
        `urls` is optional — if omitted, the agent searches the web itself.
        """
        payload: dict = {
            "prompt": prompt,
            "schema": schema,
            "model": model or CONFIG.spark_model,
        }
        if urls:
            payload["urls"] = urls
        if max_credits is not None:
            payload["maxCredits"] = max_credits

        resp = httpx.post(
            f"{self.api_url}/v2/agent",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()
