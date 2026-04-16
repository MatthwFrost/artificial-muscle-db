# artificial-muscle-db

An open, structured database of artificial-muscle / actuator materials and technologies, built by LLM-based extraction from the published literature.

Successor in spirit to Madden 2007's *Science* comparative review, refreshed to 2026+ and designed to be machine-readable, queryable, and community-extensible.

## Status

Early scaffolding. Not yet deployed. See `SCRATCHPAD.md` (in sibling `../polymer-ml/` project for now) for ongoing decisions.

## What this project is

- A Postgres-backed database with a **universal performance schema** (strain, stress, work density, efficiency, response time, cycle life, etc.) that every row carries, plus **per-class extension tables** (polymer SMILES fields, SMA alloy composition, piezoelectric crystal parameters, etc.).
- A Python extraction pipeline that uses **Firecrawl** to retrieve primary-source papers and **an LLM** (spark-1-pro tier) to parse them into rows validated against Pydantic schemas.
- A **FastAPI read API** with auto-generated OpenAPI docs.
- A human-in-the-loop validation audit trail — every extracted row carries provenance and confidence.

## Taxonomy (v0)

11 classes. See `docs/taxonomy.md` and `db/init/01_schema.sql`.

1. Electronic EAPs
2. Ionic EAPs
3. Thermally driven polymers (LCE, SMP, TCPA)
4. Stimuli-responsive gels
5. Shape memory alloys
6. Piezoelectric / ferroelectric ceramics
7. Carbon-based (CNT yarn, graphene)
8. Biohybrid
9. Pneumatic / fluidic
10. Magnetic / magnetoactive
11. Combustion / chemomechanical

## Architecture

```
[ Firecrawl API ]
        |
        v
[ worker container ] --(extract via LLM)--> [ Pydantic validation ]
        |                                            |
        v                                            v
[ Postgres ] <------------- [ extraction_audit log ]
        ^
        |
[ FastAPI read API ]
        ^
        |
[ Caddy reverse proxy + TLS ]
```

Single-host Docker Compose deployment. Postgres + Redis + worker + api + (later) Caddy.

## Repo layout

```
artificial-muscle-db/
  db/
    init/          # SQL run at first container boot (schema + seeds)
  schema/          # Pydantic / JSON-schema definitions, shared between worker and API
  worker/          # extraction pipeline
  api/             # FastAPI read API
  scripts/         # ops scripts (seed papers, export, backup)
  docs/            # taxonomy, schema rationale, extraction prompts
  tests/
  docker-compose.yml
  .env.example
```

## Deploy

TBD — requires VPS access. Target: `root@72.61.17.90` (Ubuntu 24.04, 1 CPU, 3.8GB RAM).

## License

TBD. Probably CC-BY-4.0 for the dataset, MIT for the code.
