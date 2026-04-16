"""Firecrawl v2 client: /v2/scrape and /v2/agent.

Verified against Firecrawl production 2026-04-16:

- `POST /v2/agent` returns `{success, id}` synchronously; the job runs asynchronously.
- `GET  /v2/agent/{id}` returns `{success, status, data?, error?, creditsUsed, model, expiresAt}`.
  `status` is one of: `processing` | `completed` | `failed` | `cancelled`.
- On `completed`, `data` matches the schema you passed in (or is a string if no schema).
- On `failed`, `error` contains a human-readable reason. Common cases:
  * "Refusal: I cannot access the URL ..." — the target page could not be fetched.
  * "Refusal: Error: Agent reached max credits" — the `maxCredits` ceiling was too low.
- `creditsUsed` in the response is not always reliable; the authoritative view is
  `GET /v2/team/credit-usage` which returns the team's remaining balance.
- Valid `model` values: `spark-1-pro`, `spark-1-mini`. `spark-1-fast` is rejected."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import CONFIG


class FirecrawlError(RuntimeError):
    def __init__(self, message: str, *, status: str | None = None, response: dict | None = None):
        super().__init__(message)
        self.status = status
        self.response = response or {}


@dataclass
class AgentResult:
    status: str                 # 'completed' | 'failed' | 'cancelled'
    data: Any                   # dict or string on completed, None otherwise
    error: str | None
    credits_used: int | None
    model: str
    job_id: str
    duration_s: float


class FirecrawlClient:
    def __init__(self, api_key: str | None = None, api_url: str | None = None, timeout: float = 300.0):
        self.api_key = api_key or CONFIG.firecrawl_api_key
        self.api_url = (api_url or CONFIG.firecrawl_api_url).rstrip("/")
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError("FIRECRAWL_API_KEY not set")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    # ------------------------------------------------------------------ scrape

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=30))
    def scrape(self, url: str, formats: tuple[str, ...] = ("markdown",)) -> dict:
        """Synchronous scrape. Returns the full response including `data.markdown`."""
        resp = httpx.post(
            f"{self.api_url}/v2/scrape",
            json={"url": url, "formats": list(formats)},
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------ agent

    def agent_submit(
        self,
        prompt: str,
        schema: dict | None,
        urls: list[str] | None = None,
        model: str | None = None,
        max_credits: int | None = None,
    ) -> str:
        """Submit an /agent job. Returns the job id."""
        payload: dict[str, Any] = {"prompt": prompt, "model": model or CONFIG.spark_model}
        if schema is not None:
            payload["schema"] = schema
        if urls:
            payload["urls"] = urls
        if max_credits is not None:
            payload["maxCredits"] = max_credits

        resp = httpx.post(
            f"{self.api_url}/v2/agent", json=payload, headers=self._headers(), timeout=60.0
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success") or "id" not in body:
            raise FirecrawlError(f"unexpected /agent POST response: {body}", response=body)
        return body["id"]

    def agent_poll(self, job_id: str) -> dict:
        resp = httpx.get(
            f"{self.api_url}/v2/agent/{job_id}",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()

    def agent(
        self,
        prompt: str,
        schema: dict | None = None,
        urls: list[str] | None = None,
        model: str | None = None,
        max_credits: int | None = None,
        poll_interval_s: float = 8.0,
        poll_timeout_s: float = 600.0,
    ) -> AgentResult:
        """Submit an agent job and block until it reaches a terminal state.

        Raises FirecrawlError on transport errors. Returns an AgentResult in all
        terminal cases (completed / failed / cancelled) — callers must check `.status`.
        """
        job_id = self.agent_submit(prompt, schema, urls=urls, model=model, max_credits=max_credits)
        t0 = time.monotonic()
        while True:
            if time.monotonic() - t0 > poll_timeout_s:
                raise FirecrawlError(
                    f"agent job {job_id} did not terminate within {poll_timeout_s}s",
                    status="timeout",
                )
            time.sleep(poll_interval_s)
            body = self.agent_poll(job_id)
            status = body.get("status")
            if status in {"completed", "failed", "cancelled"}:
                return AgentResult(
                    status=status,
                    data=body.get("data"),
                    error=body.get("error"),
                    credits_used=body.get("creditsUsed"),
                    model=body.get("model", model or CONFIG.spark_model),
                    job_id=job_id,
                    duration_s=time.monotonic() - t0,
                )

    # --------------------------------------------------------------- account

    def credit_usage(self) -> dict:
        resp = httpx.get(
            f"{self.api_url}/v2/team/credit-usage",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json().get("data", {})
