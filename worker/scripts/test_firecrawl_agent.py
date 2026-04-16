"""Smoke test for the Firecrawl /v2/agent + spark-1-pro contract.

Usage (on VPS, inside the worker container):
    docker compose exec worker python /app/scripts/test_firecrawl_agent.py <url>

Or locally with a populated .env:
    python scripts/test_firecrawl_agent.py <url>

The script:
1. Calls /v2/agent with our MaterialExtraction schema and the LCE prompt.
2. Prints the raw response.
3. Tries to parse the response into a list of MaterialExtraction Pydantic objects.
4. Reports which fields were populated vs left null, plus validation errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running the script directly or from inside the container where /app is on PYTHONPATH.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "worker"))

from muscle_worker.config import CONFIG  # noqa: E402
from muscle_worker.firecrawl_client import FirecrawlClient  # noqa: E402
from muscle_worker.schemas import MaterialExtraction  # noqa: E402


DEFAULT_URL = "https://www.mdpi.com/2073-4360/12/8/1857"  # MDPI Polymers LCE review, open access
LCE_PROMPT = (Path(ROOT) / "worker" / "prompts" / "lce.md").read_text()


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    print(f"[firecrawl-test] endpoint = {CONFIG.firecrawl_api_url}/v2/agent")
    print(f"[firecrawl-test] model    = {CONFIG.spark_model}")
    print(f"[firecrawl-test] url      = {url}")
    print(f"[firecrawl-test] prompt   = {len(LCE_PROMPT)} chars")
    print()

    client = FirecrawlClient()

    # Firecrawl /agent expects a single schema, not an array. If we want multiple
    # rows per paper (we do), wrap our MaterialExtraction in an envelope.
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

    print("[firecrawl-test] POST /v2/agent ...")
    try:
        resp = client.agent(
            prompt=LCE_PROMPT,
            schema=envelope_schema,
            urls=[url],
            max_credits=50,
        )
    except Exception as e:
        print(f"[firecrawl-test] REQUEST FAILED: {type(e).__name__}: {e}")
        return

    print("[firecrawl-test] raw response keys:", list(resp.keys()) if isinstance(resp, dict) else type(resp))
    print()
    print(json.dumps(resp, indent=2, default=str)[:4000])
    print()

    data = resp.get("data") if isinstance(resp, dict) else None
    if not data:
        print("[firecrawl-test] no `data` field in response; bailing.")
        return

    materials_raw = data.get("materials") if isinstance(data, dict) else None
    if materials_raw is None:
        print("[firecrawl-test] no `materials` array in data; bailing.")
        return

    print(f"[firecrawl-test] agent returned {len(materials_raw)} candidate materials")
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
        print(f"  populated fields ({len(populated)}): {', '.join(sorted(populated))}")
        print(f"  confidence={u.extraction_confidence}")


if __name__ == "__main__":
    main()
