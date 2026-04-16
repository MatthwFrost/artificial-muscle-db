"""Firecrawl API wrapper. Handles scraping, crawling, and extract-tier (spark-1-pro) calls.

NOTE: The exact shape of the Firecrawl 'extract' endpoint and the spark-1-pro model
identifier needs to be confirmed against current Firecrawl docs before wiring this in
end-to-end. This module centralizes that coupling so only one file changes when the
Firecrawl interface shifts."""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import CONFIG


class FirecrawlClient:
    def __init__(self, api_key: str | None = None, api_url: str | None = None, timeout: float = 60.0):
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
            f"{self.api_url}/v1/scrape",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=30))
    def extract(self, url_or_text: str, schema: dict, prompt: str | None = None, *, model: str | None = None) -> dict:
        """Call Firecrawl's extract/spark endpoint with a JSON schema and optional prompt.

        `schema` is a JSON-schema dict (typically from a Pydantic model via `.model_json_schema()`).
        """
        payload: dict = {
            "schema": schema,
            "model": model or CONFIG.spark_model,
        }
        if url_or_text.startswith(("http://", "https://")):
            payload["urls"] = [url_or_text]
        else:
            payload["text"] = url_or_text
        if prompt:
            payload["prompt"] = prompt

        resp = httpx.post(
            f"{self.api_url}/v1/extract",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()
