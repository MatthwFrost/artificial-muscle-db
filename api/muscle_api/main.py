"""Read-only FastAPI for the artificial-muscle-db. Admin/write endpoints come later."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Optional

import psycopg
from fastapi import FastAPI, HTTPException, Query
from psycopg.rows import dict_row


def dsn() -> str:
    return (
        f"postgresql://{os.getenv('POSTGRES_USER','muscle')}:{os.getenv('POSTGRES_PASSWORD','')}"
        f"@{os.getenv('POSTGRES_HOST','postgres')}:{os.getenv('POSTGRES_PORT','5432')}/"
        f"{os.getenv('POSTGRES_DB','muscle_db')}"
    )


@contextmanager
def conn():
    with psycopg.connect(dsn(), row_factory=dict_row) as c:
        yield c


app = FastAPI(
    title="artificial-muscle-db API",
    version="0.1.0",
    description="Open structured database of artificial-muscle / actuator materials.",
)


@app.get("/health")
def health():
    try:
        with conn() as c, c.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, f"db unreachable: {e}")


@app.get("/taxonomy")
def taxonomy():
    with conn() as c, c.cursor() as cur:
        cur.execute(
            """SELECT class_id, parent_class_id, slug, name, level, description
                 FROM taxonomy_classes
                ORDER BY COALESCE(parent_class_id, class_id), level, class_id"""
        )
        return {"classes": cur.fetchall()}


@app.get("/papers")
def list_papers(
    class_slug: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    q: Optional[str] = Query(None, description="Fuzzy title search"),
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    where = ["1=1"]
    params: list = []
    if class_slug:
        where.append("c.slug = %s")
        params.append(class_slug)
    if year_min is not None:
        where.append("p.year >= %s")
        params.append(year_min)
    if year_max is not None:
        where.append("p.year <= %s")
        params.append(year_max)
    if q:
        where.append("p.title %% %s")  # trigram similarity
        params.append(q)
    params.extend([limit, offset])

    sql = f"""
        SELECT p.paper_id, p.doi, p.title, p.authors, p.year, p.venue, p.url, c.slug AS class_slug
          FROM papers p
          LEFT JOIN taxonomy_classes c ON c.class_id = p.primary_class_id
         WHERE {' AND '.join(where)}
         ORDER BY p.year DESC NULLS LAST, p.paper_id DESC
         LIMIT %s OFFSET %s
    """
    with conn() as c, c.cursor() as cur:
        cur.execute(sql, params)
        return {"papers": cur.fetchall()}


@app.get("/materials")
def list_materials(
    class_slug: Optional[str] = None,
    stimulus: Optional[str] = None,
    strain_min_pct: Optional[float] = None,
    strain_max_pct: Optional[float] = None,
    stress_min_kpa: Optional[float] = None,
    stress_max_kpa: Optional[float] = None,
    verified_only: bool = False,
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    where = ["1=1"]
    params: list = []
    if class_slug:
        where.append("c.slug = %s")
        params.append(class_slug)
    if stimulus:
        where.append("m.stimulus = %s::stimulus_type")
        params.append(stimulus)
    if strain_min_pct is not None:
        where.append("m.actuation_strain_pct >= %s")
        params.append(strain_min_pct)
    if strain_max_pct is not None:
        where.append("m.actuation_strain_pct <= %s")
        params.append(strain_max_pct)
    if stress_min_kpa is not None:
        where.append("m.blocking_stress_kpa >= %s")
        params.append(stress_min_kpa)
    if stress_max_kpa is not None:
        where.append("m.blocking_stress_kpa <= %s")
        params.append(stress_max_kpa)
    if verified_only:
        where.append("m.verified = TRUE")
    params.extend([limit, offset])

    sql = f"""
        SELECT m.material_id, m.material_name, c.slug AS class_slug,
               m.stimulus, m.actuation_strain_pct, m.blocking_stress_kpa,
               m.work_density_kj_m3, m.response_time_s, m.cycle_life,
               m.extraction_confidence, m.verified,
               p.paper_id, p.doi, p.title AS paper_title, p.year
          FROM materials m
          JOIN taxonomy_classes c ON c.class_id = m.class_id
          JOIN papers p          ON p.paper_id = m.paper_id
         WHERE {' AND '.join(where)}
         ORDER BY m.material_id DESC
         LIMIT %s OFFSET %s
    """
    with conn() as c, c.cursor() as cur:
        cur.execute(sql, params)
        return {"materials": cur.fetchall()}


@app.get("/materials/{material_id}")
def get_material(material_id: int):
    with conn() as c, c.cursor() as cur:
        cur.execute(
            """SELECT m.*, c.slug AS class_slug, p.doi, p.title AS paper_title, p.year
                 FROM materials m
                 JOIN taxonomy_classes c ON c.class_id = m.class_id
                 JOIN papers p          ON p.paper_id = m.paper_id
                WHERE m.material_id = %s""",
            (material_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "material not found")
        return row
