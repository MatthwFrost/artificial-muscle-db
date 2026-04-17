"""Smoke test for the Firecrawl /v2/agent + spark-1-pro contract.

Run inside the worker container:
    docker compose exec worker python /app/scripts/test_firecrawl_agent.py [url]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from muscle_worker.config import CONFIG
from muscle_worker.firecrawl_client import FirecrawlClient


DEFAULT_URL = "https://en.wikipedia.org/wiki/Liquid_crystal_elastomer"
PROMPTS_DIR = Path("/app/prompts")
SCHEMAS_DIR = Path("/app/schemas/firecrawl")


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    prompt = (PROMPTS_DIR / "lce.md").read_text()
    schema = json.loads((SCHEMAS_DIR / "lce.json").read_text())

    print(f"[test] endpoint = {CONFIG.firecrawl_api_url}/v2/agent")
    print(f"[test] model    = {CONFIG.spark_model}")
    print(f"[test] url      = {url}")
    print(f"[test] schema   = lce.json ({len(json.dumps(schema))} chars)")
    print()

    client = FirecrawlClient()

    print(f"[test] credits before: {client.credit_usage()}")
    print()
    print("[test] submitting agent job...")
    result = client.agent(prompt=prompt, schema=schema, urls=[url])

    print(f"[test] job_id       = {result.job_id}")
    print(f"[test] status       = {result.status}")
    print(f"[test] duration     = {result.duration_s:.1f}s")
    print(f"[test] credits used = {result.credits_used}")
    if result.error:
        print(f"[test] error        = {result.error}")
    print()

    if result.status != "completed":
        print("[test] job did not complete.")
        print(f"[test] credits after: {client.credit_usage()}")
        return

    print("=== RAW DATA ===")
    print(json.dumps(result.data, indent=2)[:5000])
    print()

    materials = (result.data or {}).get("materials") or []
    print(f"[test] {len(materials)} material(s) extracted")
    for i, m in enumerate(materials, 1):
        populated = {k: v for k, v in m.items() if v is not None}
        print(f"  [{i}] {m.get('material_name','?')} — {len(populated)} fields, confidence={m.get('extraction_confidence')}")

    print()
    print(f"[test] credits after: {client.credit_usage()}")


if __name__ == "__main__":
    main()
