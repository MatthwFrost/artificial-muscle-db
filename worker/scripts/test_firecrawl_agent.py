"""Smoke test for the Firecrawl /v2/agent + spark-1-pro contract, using our client.

Run inside the worker container:
    docker compose exec worker python /app/scripts/test_firecrawl_agent.py [url]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from muscle_worker.config import CONFIG
from muscle_worker.firecrawl_client import FirecrawlClient
from muscle_worker.schemas import MaterialExtraction


DEFAULT_URL = "https://en.wikipedia.org/wiki/Liquid_crystal_elastomer"
PROMPTS_DIR = Path("/app/prompts")


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    prompt = (PROMPTS_DIR / "lce.md").read_text()

    print(f"[test] endpoint = {CONFIG.firecrawl_api_url}/v2/agent")
    print(f"[test] model    = {CONFIG.spark_model}")
    print(f"[test] url      = {url}")
    print()

    client = FirecrawlClient()

    envelope_schema = {
        "type": "object",
        "properties": {
            "materials": {
                "type": "array",
                "items": MaterialExtraction.model_json_schema(),
            }
        },
        "required": ["materials"],
    }

    print(f"[test] credits before: {client.credit_usage()}")
    print()
    print("[test] submitting agent job (no maxCredits cap)...")
    result = client.agent(prompt=prompt, schema=envelope_schema, urls=[url])

    print(f"[test] job_id       = {result.job_id}")
    print(f"[test] status       = {result.status}")
    print(f"[test] duration     = {result.duration_s:.1f}s")
    print(f"[test] credits used = {result.credits_used}")
    if result.error:
        print(f"[test] error        = {result.error}")
    print()

    if result.status != "completed":
        print("[test] job did not complete; stopping here.")
        print(f"[test] credits after: {client.credit_usage()}")
        return

    materials_raw = (result.data or {}).get("materials") or []
    print(f"[test] agent returned {len(materials_raw)} candidate material(s)")
    print()

    for i, item in enumerate(materials_raw, 1):
        print(f"--- material {i} ---")
        try:
            m = MaterialExtraction.model_validate(item)
        except Exception as e:
            print(f"  pydantic validation FAILED: {e}")
            print(f"  raw item: {json.dumps(item)[:400]}")
            continue
        ext_errs = m.validate_extension_matches_class()
        if ext_errs:
            print(f"  extension/class mismatch: {ext_errs}")
        u = m.universal
        populated = {k: v for k, v in u.model_dump().items() if v not in (None, [], "")}
        print(f"  class_slug={u.class_slug} subclass_slug={u.subclass_slug}")
        print(f"  populated ({len(populated)}): {', '.join(sorted(populated))}")
        print(f"  confidence={u.extraction_confidence}")

    print()
    print(f"[test] credits after: {client.credit_usage()}")


if __name__ == "__main__":
    main()
