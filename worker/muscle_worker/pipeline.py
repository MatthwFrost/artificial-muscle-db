"""Extraction pipeline: URL → Firecrawl /v2/agent → DB insert + audit.

Orchestrates the full flow for a single paper:
1. Load the prompt and flat schema for the target class.
2. Submit to Firecrawl's /v2/agent endpoint and wait for completion.
3. Map each extracted material (flat dict) into the materials table + extension table.
4. Write an audit record per material.
5. Update the paper's extraction_status.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from . import __version__
from .config import CONFIG
from .db import (
    insert_extraction_audit,
    insert_material_from_flat,
    update_paper_status,
    upsert_paper_from_url,
)
from .firecrawl_client import AgentResult, FirecrawlClient

log = structlog.get_logger()

PROMPTS_DIR = Path("/app/prompts")
SCHEMAS_DIR = Path("/app/schemas/firecrawl")


@dataclass
class ExtractionResult:
    paper_id: int
    url: str
    class_slug: str
    status: str                           # 'completed' | 'failed' | 'error'
    materials_inserted: int = 0
    material_ids: list[int] = field(default_factory=list)
    credits_used: int | None = None
    duration_s: float = 0.0
    error: str | None = None


def _load_prompt(class_slug: str) -> str:
    specific = PROMPTS_DIR / f"{class_slug}.md"
    if specific.exists():
        return specific.read_text()
    return (PROMPTS_DIR / "default.md").read_text()


def _load_schema(class_slug: str) -> dict:
    specific = SCHEMAS_DIR / f"{class_slug}.json"
    if specific.exists():
        return json.loads(specific.read_text())
    raise FileNotFoundError(
        f"No Firecrawl schema for class '{class_slug}'. "
        f"Create {specific} before extracting this class."
    )


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


# Maps Firecrawl class_slug names that appear in the schema to
# (top-level taxonomy slug, subclass slug).
# The LCE prompt tells the model to use class_slug="thermal_polymer" / subclass="lce".
SUBCLASS_DEFAULTS: dict[str, tuple[str, str | None]] = {
    "lce": ("thermal_polymer", "lce"),
    "smp": ("thermal_polymer", "smp"),
    "tcpa": ("thermal_polymer", "tcpa"),
    "dea": ("electronic_eap", "dea"),
}


def extract_paper(
    url: str,
    class_slug: str,
    *,
    title: str = "Untitled",
    client: FirecrawlClient | None = None,
    subclass_slug: str | None = None,
) -> ExtractionResult:
    """Run the full pipeline for one paper URL."""
    client = client or FirecrawlClient()
    result = ExtractionResult(paper_id=0, url=url, class_slug=class_slug, status="error")

    try:
        prompt = _load_prompt(class_slug)
        schema = _load_schema(class_slug)
    except FileNotFoundError as e:
        result.error = str(e)
        log.error("schema_not_found", class_slug=class_slug, err=str(e))
        return result

    paper_id = upsert_paper_from_url(url, title=title, class_slug=class_slug)
    result.paper_id = paper_id
    log.info("paper_upserted", paper_id=paper_id, url=url)

    agent_result: AgentResult = client.agent(prompt=prompt, schema=schema, urls=[url])
    result.credits_used = agent_result.credits_used
    result.duration_s = agent_result.duration_s

    if agent_result.status != "completed":
        result.status = "failed"
        result.error = agent_result.error or f"agent status: {agent_result.status}"
        update_paper_status(paper_id, "error")
        insert_extraction_audit(
            paper_id, None,
            extractor_version=f"muscle-extractor/{__version__}",
            model=agent_result.model,
            class_extractor=class_slug,
            prompt_hash=_prompt_hash(prompt),
            raw_output=json.dumps(agent_result.data, default=str) if agent_result.data else agent_result.error,
            validation_status="rejected",
            validation_errors=[result.error],
            duration_ms=int(agent_result.duration_s * 1000),
        )
        log.warning("extraction_failed", paper_id=paper_id, error=result.error)
        return result

    materials_raw = (agent_result.data or {}).get("materials") or []
    log.info("extraction_completed", paper_id=paper_id, n_materials=len(materials_raw),
             credits=agent_result.credits_used, duration=f"{agent_result.duration_s:.1f}s")

    for mat in materials_raw:
        try:
            top_slug = class_slug
            sub_slug = subclass_slug
            if sub_slug is None and class_slug in SUBCLASS_DEFAULTS:
                top_slug, sub_slug = SUBCLASS_DEFAULTS[class_slug]

            mid = insert_material_from_flat(paper_id, mat, top_slug, sub_slug)
            result.material_ids.append(mid)
            result.materials_inserted += 1

            insert_extraction_audit(
                paper_id, mid,
                extractor_version=f"muscle-extractor/{__version__}",
                model=agent_result.model,
                class_extractor=class_slug,
                prompt_hash=_prompt_hash(prompt),
                raw_output=json.dumps(mat, default=str),
                parsed_json=mat,
                validation_status="passed",
                duration_ms=int(agent_result.duration_s * 1000),
            )
            log.info("material_inserted", paper_id=paper_id, material_id=mid,
                     name=mat.get("material_name"))

        except Exception as e:
            log.error("material_insert_failed", paper_id=paper_id, err=str(e), raw=mat)
            insert_extraction_audit(
                paper_id, None,
                extractor_version=f"muscle-extractor/{__version__}",
                model=agent_result.model,
                class_extractor=class_slug,
                prompt_hash=_prompt_hash(prompt),
                raw_output=json.dumps(mat, default=str),
                validation_status="schema_fail",
                validation_errors=[str(e)],
                duration_ms=int(agent_result.duration_s * 1000),
            )

    update_paper_status(paper_id, "verified" if result.materials_inserted > 0 else "error")
    result.status = "completed" if result.materials_inserted > 0 else "failed"
    return result
