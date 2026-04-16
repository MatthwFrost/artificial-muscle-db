"""Smoke test for the Firecrawl /v2/agent + spark-1-pro contract.

Run inside the worker container:
    docker compose exec worker python /app/scripts/test_firecrawl_agent.py [url]

The script:
1. Calls /v2/agent with our MaterialExtraction schema and the LCE prompt.
2. Prints a trimmed raw response.
3. Tries to parse the response into MaterialExtraction Pydantic objects.
4. Reports populated fields, confidence, and any validation errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from muscle_worker.config import CONFIG
from muscle_worker.firecrawl_client import FirecrawlClient
from muscle_worker.schemas import MaterialExtraction


DEFAULT_URL = "https://www.mdpi.com/2073-4360/12/8/1857"  # MDPI Polymers LCE review (open access)
PROMPTS_DIR = Path("/app/prompts")


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    prompt = (PROMPTS_DIR / "lce.md").read_text()

    print(f"[test] endpoint = {CONFIG.firecrawl_api_url}/v2/agent")
    print(f"[test] model    = {CONFIG.spark_model}")
    print(f"[test] url      = {url}")
    print(f"[test] prompt   = {len(prompt)} chars")
    print()

    client = FirecrawlClient()

    # /agent takes a single schema. We wrap MaterialExtraction in an envelope so
    # one paper can produce multiple material rows.
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

    print("[test] POST /v2/agent ...")
    try:
        resp = client.agent(
            prompt=prompt,
            schema=envelope_schema,
            urls=[url],
            max_credits=50,
        )
    except Exception as e:
        print(f"[test] REQUEST FAILED: {type(e).__name__}: {e}")
        if hasattr(e, "response") and getattr(e, "response", None) is not None:
            print(f"[test] response status: {e.response.status_code}")
            print(f"[test] response body:   {e.response.text[:2000]}")
        return

    print("[test] response top-level keys:", list(resp.keys()) if isinstance(resp, dict) else type(resp))
    print()
    print(json.dumps(resp, indent=2, default=str)[:4000])
    print()

    data = resp.get("data") if isinstance(resp, dict) else None
    if data is None:
        print("[test] no `data` field in response; stopping here.")
        return

    materials_raw = data.get("materials") if isinstance(data, dict) else None
    if materials_raw is None:
        print("[test] no `materials` array in data; stopping here.")
        return

    print(f"[test] agent returned {len(materials_raw)} candidate material(s)")
    print()

    for i, item in enumerate(materials_raw, 1):
        print(f"--- material {i} ---")
        try:
            m = MaterialExtraction.model_validate(item)
        except Exception as e:
            print(f"  pydantic validation FAILED: {e}")
            continue
        ext_errs = m.validate_extension_matches_class()
        if ext_errs:
            print(f"  extension/class mismatch: {ext_errs}")

        u = m.universal
        populated = {k: v for k, v in u.model_dump().items() if v not in (None, [], "")}
        print(f"  class_slug={u.class_slug} subclass_slug={u.subclass_slug}")
        print(f"  populated ({len(populated)}): {', '.join(sorted(populated))}")
        print(f"  confidence={u.extraction_confidence}")


if __name__ == "__main__":
    main()
