"""Class-specific extraction logic. Each class gets its own prompt template; universal
fields are always requested. Extractor returns validated MaterialExtraction objects and
records the audit trail."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import orjson
import structlog

from .firecrawl_client import FirecrawlClient
from .schemas import CLASS_EXTENSION_MAP, MaterialExtraction, PaperRecord

log = structlog.get_logger()

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(class_slug: str) -> str:
    path = PROMPTS_DIR / f"{class_slug}.md"
    if path.exists():
        return path.read_text()
    return (PROMPTS_DIR / "default.md").read_text()


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


class Extractor:
    def __init__(self, firecrawl: FirecrawlClient):
        self.firecrawl = firecrawl

    def extract_from_paper(self, paper: PaperRecord, class_slug: str) -> list[MaterialExtraction]:
        """Run extraction on a paper and return validated material rows.

        Returns an empty list if extraction failed or produced nothing valid.
        """
        if paper.full_text_md is None:
            log.warning("no_full_text", paper_title=paper.title)
            return []

        prompt = load_prompt(class_slug)
        schema = MaterialExtraction.model_json_schema()

        raw = self.firecrawl.extract(paper.full_text_md, schema=schema, prompt=prompt)
        results_raw = raw.get("data") or raw.get("results") or []
        if isinstance(results_raw, dict):
            results_raw = [results_raw]

        results: list[MaterialExtraction] = []
        for item in results_raw:
            try:
                m = MaterialExtraction.model_validate(item)
            except Exception as e:
                log.warning("extraction_validation_failed", err=str(e), item=item)
                continue
            ext_errs = m.validate_extension_matches_class()
            if ext_errs:
                log.warning("extension_class_mismatch", errors=ext_errs)
                continue
            results.append(m)
        return results

    def dump_json(self, extractions: Iterable[MaterialExtraction]) -> bytes:
        return orjson.dumps([e.model_dump(mode="json") for e in extractions])
