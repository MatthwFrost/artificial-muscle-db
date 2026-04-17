"""Thin Postgres wrapper. All SQL by hand (no ORM)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from .config import CONFIG
from .schemas import MaterialExtraction, PaperRecord


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(CONFIG.postgres_dsn, row_factory=dict_row) as conn:
        yield conn


def get_class_id(slug: str) -> int | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT class_id FROM taxonomy_classes WHERE slug = %s", (slug,))
        row = cur.fetchone()
        return row["class_id"] if row else None


def resolve_class_slug(class_slug: str, subclass_slug: str | None) -> tuple[int, int | None]:
    class_id = get_class_id(class_slug)
    if class_id is None:
        raise ValueError(f"unknown class_slug: {class_slug}")
    subclass_id = get_class_id(subclass_slug) if subclass_slug else None
    return class_id, subclass_id


# ------------------------------------------------------------------ papers

def upsert_paper(paper: PaperRecord) -> int:
    with get_conn() as conn, conn.cursor() as cur:
        primary_class_id = get_class_id(paper.primary_class_slug) if paper.primary_class_slug else None
        cur.execute(
            """
            INSERT INTO papers (doi, arxiv_id, title, authors, year, venue, url, pdf_url,
                                abstract, full_text_md, primary_class_id, seed_source,
                                extraction_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'extracting'::extraction_status)
            ON CONFLICT (doi) DO UPDATE SET
                title = COALESCE(EXCLUDED.title, papers.title),
                authors = COALESCE(EXCLUDED.authors, papers.authors),
                year = COALESCE(EXCLUDED.year, papers.year),
                venue = COALESCE(EXCLUDED.venue, papers.venue),
                url = COALESCE(EXCLUDED.url, papers.url),
                pdf_url = COALESCE(EXCLUDED.pdf_url, papers.pdf_url),
                abstract = COALESCE(EXCLUDED.abstract, papers.abstract),
                full_text_md = COALESCE(EXCLUDED.full_text_md, papers.full_text_md),
                primary_class_id = COALESCE(EXCLUDED.primary_class_id, papers.primary_class_id),
                extraction_status = 'extracting'::extraction_status
            RETURNING paper_id
            """,
            (paper.doi, paper.arxiv_id, paper.title, paper.authors, paper.year,
             paper.venue, paper.url, paper.pdf_url, paper.abstract, paper.full_text_md,
             primary_class_id, paper.seed_source),
        )
        conn.commit()
        return cur.fetchone()["paper_id"]


def upsert_paper_from_url(url: str, title: str, class_slug: str | None = None) -> int:
    """Minimal paper insert from just a URL + title. Returns paper_id."""
    p = PaperRecord(title=title, url=url, primary_class_slug=class_slug, seed_source="pipeline")
    return upsert_paper(p)


def update_paper_status(paper_id: int, status: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE papers SET extraction_status = %s::extraction_status WHERE paper_id = %s",
            (status, paper_id),
        )
        conn.commit()


# ------------------------------------------------------------------ materials (flat dict path)

UNIVERSAL_FIELDS = {
    "material_name", "stimulus", "drive_magnitude_value", "drive_magnitude_unit",
    "actuation_strain_pct", "blocking_stress_kpa", "work_density_kj_m3",
    "power_density_w_kg", "response_time_s", "cycle_life", "efficiency_pct",
    "operating_t_min_c", "operating_t_max_c", "youngs_modulus_mpa", "trl",
    "extraction_confidence", "notes",
}

POLYMER_EXTENSION_FIELDS = {
    "backbone_smiles", "mesogen_smiles", "crosslinker_smiles", "spacer_smiles",
    "endcap_smiles", "dopant_smiles", "mol_pct_crosslinker", "mol_pct_mesogen",
    "glass_transition_c", "nematic_iso_c", "mn_g_mol", "mw_g_mol", "pdi",
    "crosslink_density", "dielectric_constant", "breakdown_strength_mv_m",
}

POLYMER_CLASSES = {"electronic_eap", "ionic_eap", "thermal_polymer", "gel"}

# Map of class_slug -> (extension table name, set of column names)
CLASS_EXTENSION_TABLES: dict[str, tuple[str, set[str]]] = {
    slug: ("materials_polymer", POLYMER_EXTENSION_FIELDS) for slug in POLYMER_CLASSES
}


def insert_material_from_flat(
    paper_id: int,
    flat: dict[str, Any],
    class_slug: str,
    subclass_slug: str | None = None,
) -> int:
    """Insert a material row from a flat dict (as returned by Firecrawl).
    Splits the dict into universal fields + extension fields automatically.
    Returns material_id.
    """
    class_id, subclass_id = resolve_class_slug(class_slug, subclass_slug)

    stimulus_raw = flat.get("stimulus", "unknown")
    valid_stimuli = {
        "electric_field", "electric_current", "thermal", "optical",
        "chemical_ph", "chemical_solvent", "humidity", "magnetic",
        "pneumatic", "mechanical", "combustion", "multi", "unknown",
    }
    stimulus = stimulus_raw if stimulus_raw in valid_stimuli else "unknown"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO materials (
                paper_id, class_id, subclass_id,
                material_name, stimulus,
                drive_magnitude_value, drive_magnitude_unit,
                actuation_strain_pct, blocking_stress_kpa, work_density_kj_m3,
                power_density_w_kg, response_time_s, cycle_life, efficiency_pct,
                operating_t_min_c, operating_t_max_c, youngs_modulus_mpa, trl,
                extraction_confidence, notes
            )
            VALUES (%s, %s, %s, %s, %s::stimulus_type, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING material_id
            """,
            (
                paper_id, class_id, subclass_id,
                flat.get("material_name"), stimulus,
                flat.get("drive_magnitude_value"), flat.get("drive_magnitude_unit"),
                flat.get("actuation_strain_pct"), flat.get("blocking_stress_kpa"),
                flat.get("work_density_kj_m3"), flat.get("power_density_w_kg"),
                flat.get("response_time_s"), flat.get("cycle_life"),
                flat.get("efficiency_pct"), flat.get("operating_t_min_c"),
                flat.get("operating_t_max_c"), flat.get("youngs_modulus_mpa"),
                flat.get("trl"), flat.get("extraction_confidence"),
                flat.get("notes"),
            ),
        )
        material_id = cur.fetchone()["material_id"]

        ext = CLASS_EXTENSION_TABLES.get(class_slug)
        if ext:
            table_name, ext_fields = ext
            ext_data = {k: flat.get(k) for k in ext_fields if flat.get(k) is not None}
            if ext_data:
                cols = ["material_id"] + list(ext_data.keys())
                placeholders = ", ".join(["%s"] * len(cols))
                col_str = ", ".join(cols)
                cur.execute(
                    f"INSERT INTO {table_name} ({col_str}) VALUES ({placeholders})",
                    [material_id] + list(ext_data.values()),
                )

        conn.commit()
        return material_id


# ------------------------------------------------------------------ audit

def insert_extraction_audit(
    paper_id: int,
    material_id: int | None,
    *,
    extractor_version: str,
    model: str,
    class_extractor: str | None = None,
    prompt_hash: str | None = None,
    raw_output: str | None = None,
    parsed_json: dict | None = None,
    validation_status: str = "passed",
    validation_errors: list[str] | None = None,
    cost_usd: float | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    duration_ms: int | None = None,
) -> int:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO extraction_audit (
                paper_id, material_id, extractor_version, model, class_extractor,
                prompt_hash, raw_output, parsed_json, validation_status,
                validation_errors, cost_usd, tokens_in, tokens_out, duration_ms
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING audit_id
            """,
            (
                paper_id, material_id, extractor_version, model, class_extractor,
                prompt_hash, raw_output,
                json.dumps(parsed_json) if parsed_json else None,
                validation_status, validation_errors or [],
                cost_usd, tokens_in, tokens_out, duration_ms,
            ),
        )
        conn.commit()
        return cur.fetchone()["audit_id"]


# ------------------------------------------------------------------ legacy (Pydantic-based path, kept for completeness)

def insert_material(paper_id: int, extraction: MaterialExtraction) -> int:
    u = extraction.universal
    class_id = get_class_id(u.class_slug)
    if class_id is None:
        raise ValueError(f"unknown class_slug: {u.class_slug}")
    subclass_id = get_class_id(u.subclass_slug) if u.subclass_slug else None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO materials (
                paper_id, class_id, subclass_id,
                material_name, material_aliases, stimulus,
                drive_magnitude_value, drive_magnitude_unit,
                actuation_strain_pct, blocking_stress_kpa, work_density_kj_m3,
                power_density_w_kg, response_time_s, cycle_life, efficiency_pct,
                operating_t_min_c, operating_t_max_c, youngs_modulus_mpa, trl,
                extraction_confidence, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s::stimulus_type, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING material_id
            """,
            (
                paper_id, class_id, subclass_id,
                u.material_name, u.material_aliases, u.stimulus.value,
                u.drive_magnitude_value, u.drive_magnitude_unit,
                u.actuation_strain_pct, u.blocking_stress_kpa, u.work_density_kj_m3,
                u.power_density_w_kg, u.response_time_s, u.cycle_life, u.efficiency_pct,
                u.operating_t_min_c, u.operating_t_max_c, u.youngs_modulus_mpa, u.trl,
                u.extraction_confidence, u.notes,
            ),
        )
        material_id = cur.fetchone()["material_id"]
        conn.commit()
        return material_id
