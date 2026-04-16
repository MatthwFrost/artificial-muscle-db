"""Thin Postgres wrapper. Opens a pooled connection on demand. All SQL is written by hand
(no ORM) to keep the extraction pipeline's data model obvious."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

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


def upsert_paper(paper: PaperRecord) -> int:
    """Insert or update a paper row, return paper_id."""
    with get_conn() as conn, conn.cursor() as cur:
        primary_class_id = get_class_id(paper.primary_class_slug) if paper.primary_class_slug else None
        cur.execute(
            """
            INSERT INTO papers (doi, arxiv_id, title, authors, year, venue, url, pdf_url,
                                abstract, full_text_md, primary_class_id, seed_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (doi) DO UPDATE SET
                title = EXCLUDED.title,
                authors = EXCLUDED.authors,
                year = EXCLUDED.year,
                venue = EXCLUDED.venue,
                url = EXCLUDED.url,
                pdf_url = EXCLUDED.pdf_url,
                abstract = EXCLUDED.abstract,
                full_text_md = EXCLUDED.full_text_md,
                primary_class_id = EXCLUDED.primary_class_id
            RETURNING paper_id
            """,
            (
                paper.doi,
                paper.arxiv_id,
                paper.title,
                paper.authors,
                paper.year,
                paper.venue,
                paper.url,
                paper.pdf_url,
                paper.abstract,
                paper.full_text_md,
                primary_class_id,
                paper.seed_source,
            ),
        )
        conn.commit()
        return cur.fetchone()["paper_id"]


def insert_material(paper_id: int, extraction: MaterialExtraction) -> int:
    """Insert a materials row + the appropriate extension row. Returns material_id."""
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
        _insert_extension(cur, material_id, u.class_slug, extraction)
        conn.commit()
        return material_id


def _insert_extension(cur, material_id: int, class_slug: str, extraction: MaterialExtraction) -> None:
    """Insert the appropriate extension row based on class_slug."""
    if class_slug in {"electronic_eap", "ionic_eap", "thermal_polymer", "gel"} and extraction.polymer:
        p = extraction.polymer
        cur.execute(
            """INSERT INTO materials_polymer (
                material_id, backbone_smiles, mesogen_smiles, crosslinker_smiles,
                spacer_smiles, endcap_smiles, dopant_smiles,
                mol_pct_crosslinker, mol_pct_mesogen,
                glass_transition_c, nematic_iso_c, mn_g_mol, mw_g_mol, pdi,
                crosslink_density, dielectric_constant, breakdown_strength_mv_m)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (material_id, p.backbone_smiles, p.mesogen_smiles, p.crosslinker_smiles,
             p.spacer_smiles, p.endcap_smiles, p.dopant_smiles,
             p.mol_pct_crosslinker, p.mol_pct_mesogen,
             p.glass_transition_c, p.nematic_iso_c, p.mn_g_mol, p.mw_g_mol, p.pdi,
             p.crosslink_density, p.dielectric_constant, p.breakdown_strength_mv_m),
        )
    elif class_slug == "sma" and extraction.sma:
        s = extraction.sma
        cur.execute(
            """INSERT INTO materials_sma (
                material_id, alloy_composition, transformation_t_c,
                austenite_start_c, austenite_finish_c, martensite_start_c, martensite_finish_c,
                hysteresis_c, training_method, is_magnetic_sma)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (material_id, s.alloy_composition, s.transformation_t_c,
             s.austenite_start_c, s.austenite_finish_c, s.martensite_start_c, s.martensite_finish_c,
             s.hysteresis_c, s.training_method, s.is_magnetic_sma),
        )
    elif class_slug == "piezo" and extraction.piezo:
        p = extraction.piezo
        cur.execute(
            """INSERT INTO materials_piezo (
                material_id, formula, crystal_structure, d33_pc_n, d31_pc_n,
                k33, kt, curie_t_c, poling_field_kv_mm, is_single_crystal)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (material_id, p.formula, p.crystal_structure, p.d33_pc_n, p.d31_pc_n,
             p.k33, p.kt, p.curie_t_c, p.poling_field_kv_mm, p.is_single_crystal),
        )
    elif class_slug == "carbon" and extraction.cnt:
        c = extraction.cnt
        cur.execute(
            """INSERT INTO materials_cnt (
                material_id, cnt_type, diameter_nm, length_mm, twist_angle_deg,
                coiling, infiltrant, bias_voltage_v)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (material_id, c.cnt_type, c.diameter_nm, c.length_mm, c.twist_angle_deg,
             c.coiling, c.infiltrant, c.bias_voltage_v),
        )
    elif class_slug == "biohybrid" and extraction.biohybrid:
        b = extraction.biohybrid
        cur.execute(
            """INSERT INTO materials_biohybrid (
                material_id, cell_type, cell_source, scaffold_material, scaffold_geometry,
                culture_days, is_optogenetic, stimulation_mode)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (material_id, b.cell_type, b.cell_source, b.scaffold_material, b.scaffold_geometry,
             b.culture_days, b.is_optogenetic, b.stimulation_mode),
        )
    elif class_slug == "pneumatic" and extraction.pneumatic:
        pn = extraction.pneumatic
        cur.execute(
            """INSERT INTO materials_pneumatic (
                material_id, geometry, chamber_material, reinforcement,
                working_fluid, max_pressure_kpa, contraction_ratio)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (material_id, pn.geometry, pn.chamber_material, pn.reinforcement,
             pn.working_fluid, pn.max_pressure_kpa, pn.contraction_ratio),
        )
    elif class_slug == "magnetic" and extraction.magnetic:
        mg = extraction.magnetic
        cur.execute(
            """INSERT INTO materials_magnetic (
                material_id, matrix_material, magnetic_filler, filler_volume_fraction,
                remanence_mt, applied_field_mt)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (material_id, mg.matrix_material, mg.magnetic_filler, mg.filler_volume_fraction,
             mg.remanence_mt, mg.applied_field_mt),
        )
