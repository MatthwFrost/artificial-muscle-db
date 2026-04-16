-- ============================================================================
-- artificial-muscle-db — schema v0
-- ============================================================================
-- Design principles:
--   1. Every material row carries a "universal" set of performance metrics so
--      cross-class comparisons are always possible.
--   2. Per-class extension tables hold physics-specific fields (polymer SMILES,
--      SMA composition, piezo constants, etc.).
--   3. Every row has provenance: which paper, which extractor, confidence, and
--      whether a human has verified it.
--   4. JSONB "extra" columns everywhere so we can add fields during research
--      without migrations blocking fieldwork.
-- ============================================================================

SET client_encoding = 'UTF8';
SET timezone = 'UTC';

CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- fuzzy text search on titles/authors
CREATE EXTENSION IF NOT EXISTS citext;    -- case-insensitive text (DOIs etc.)

-- ----------------------------------------------------------------------------
-- Enums
-- ----------------------------------------------------------------------------

CREATE TYPE stimulus_type AS ENUM (
    'electric_field',
    'electric_current',
    'thermal',
    'optical',
    'chemical_ph',
    'chemical_solvent',
    'humidity',
    'magnetic',
    'pneumatic',
    'mechanical',
    'combustion',
    'multi',
    'unknown'
);

CREATE TYPE extraction_status AS ENUM (
    'pending',
    'crawling',
    'extracting',
    'validating',
    'verified',
    'rejected',
    'error'
);

CREATE TYPE validator_type AS ENUM (
    'llm_self',
    'llm_second',
    'human',
    'rule_based'
);

-- ----------------------------------------------------------------------------
-- Taxonomy
-- ----------------------------------------------------------------------------
-- Hierarchical (11 top-level classes, each with subclasses).
-- Seeded by 02_seed_taxonomy.sql.
-- ----------------------------------------------------------------------------

CREATE TABLE taxonomy_classes (
    class_id         SERIAL PRIMARY KEY,
    parent_class_id  INTEGER REFERENCES taxonomy_classes(class_id),
    slug             TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    level            INTEGER NOT NULL,
    description      TEXT,
    canonical_materials TEXT[],
    search_keywords  TEXT[],
    canonical_review_dois CITEXT[],
    extension_table  TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_taxonomy_parent ON taxonomy_classes(parent_class_id);
CREATE INDEX idx_taxonomy_level  ON taxonomy_classes(level);

-- ----------------------------------------------------------------------------
-- Papers (source documents)
-- ----------------------------------------------------------------------------

CREATE TABLE papers (
    paper_id         SERIAL PRIMARY KEY,
    doi              CITEXT UNIQUE,
    arxiv_id         CITEXT UNIQUE,
    title            TEXT NOT NULL,
    authors          TEXT[] NOT NULL DEFAULT '{}',
    year             INTEGER,
    venue            TEXT,
    url              TEXT,
    pdf_url          TEXT,
    abstract         TEXT,
    full_text_md     TEXT,              -- markdown from firecrawl
    full_text_hash   TEXT,              -- sha256 of full_text_md
    primary_class_id INTEGER REFERENCES taxonomy_classes(class_id),
    crawled_at       TIMESTAMPTZ,
    extraction_status extraction_status NOT NULL DEFAULT 'pending',
    seed_source      TEXT,              -- 'hand_seed', 'firecrawl_search', 'doi_list'
    extra            JSONB NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_papers_title_trgm     ON papers USING GIN (title gin_trgm_ops);
CREATE INDEX idx_papers_authors        ON papers USING GIN (authors);
CREATE INDEX idx_papers_year           ON papers(year);
CREATE INDEX idx_papers_class          ON papers(primary_class_id);
CREATE INDEX idx_papers_status         ON papers(extraction_status);
CREATE INDEX idx_papers_extra          ON papers USING GIN (extra);

-- ----------------------------------------------------------------------------
-- Materials — master table with universal performance schema
-- ----------------------------------------------------------------------------

CREATE TABLE materials (
    material_id          SERIAL PRIMARY KEY,
    paper_id             INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    class_id             INTEGER NOT NULL REFERENCES taxonomy_classes(class_id),
    subclass_id          INTEGER REFERENCES taxonomy_classes(class_id),

    -- Identity
    material_name        TEXT,                          -- paper-assigned name
    material_aliases     TEXT[] NOT NULL DEFAULT '{}',

    -- Stimulus and drive
    stimulus             stimulus_type NOT NULL DEFAULT 'unknown',
    drive_magnitude_value NUMERIC,
    drive_magnitude_unit TEXT,

    -- Universal performance metrics (numeric NUMERIC, SI-ish)
    actuation_strain_pct       NUMERIC,       -- %
    blocking_stress_kpa        NUMERIC,       -- kPa
    work_density_kj_m3         NUMERIC,       -- kJ/m^3
    power_density_w_kg         NUMERIC,       -- W/kg
    response_time_s            NUMERIC,       -- s
    cycle_life                 INTEGER,       -- cycles
    efficiency_pct             NUMERIC,       -- %
    operating_t_min_c          NUMERIC,       -- °C
    operating_t_max_c          NUMERIC,       -- °C
    youngs_modulus_mpa         NUMERIC,
    trl                        SMALLINT CHECK (trl BETWEEN 1 AND 9),

    -- Provenance
    extraction_confidence      NUMERIC CHECK (extraction_confidence BETWEEN 0 AND 1),
    verified                   BOOLEAN NOT NULL DEFAULT FALSE,
    verified_by                TEXT,
    verified_at                TIMESTAMPTZ,

    -- Raw + notes
    notes                      TEXT,
    extra                      JSONB NOT NULL DEFAULT '{}',

    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_materials_paper       ON materials(paper_id);
CREATE INDEX idx_materials_class       ON materials(class_id);
CREATE INDEX idx_materials_subclass    ON materials(subclass_id);
CREATE INDEX idx_materials_stimulus    ON materials(stimulus);
CREATE INDEX idx_materials_strain      ON materials(actuation_strain_pct);
CREATE INDEX idx_materials_stress      ON materials(blocking_stress_kpa);
CREATE INDEX idx_materials_verified    ON materials(verified);
CREATE INDEX idx_materials_extra       ON materials USING GIN (extra);

-- ----------------------------------------------------------------------------
-- Extension tables — one per class that has class-specific fields.
-- Each references a material row 1:1 via material_id.
-- ----------------------------------------------------------------------------

-- Polymer-based classes (electronic EAP, ionic EAP, thermally-driven polymers,
-- stimuli-responsive gels) share this extension.
CREATE TABLE materials_polymer (
    material_id          INTEGER PRIMARY KEY REFERENCES materials(material_id) ON DELETE CASCADE,
    backbone_smiles      TEXT,
    mesogen_smiles       TEXT,
    crosslinker_smiles   TEXT,
    spacer_smiles        TEXT,
    endcap_smiles        TEXT,
    dopant_smiles        TEXT,
    mol_pct_crosslinker  NUMERIC,
    mol_pct_mesogen      NUMERIC,
    glass_transition_c   NUMERIC,    -- Tg
    nematic_iso_c        NUMERIC,    -- Tni (LCE only)
    mn_g_mol             NUMERIC,
    mw_g_mol             NUMERIC,
    pdi                  NUMERIC,
    crosslink_density    NUMERIC,
    dielectric_constant  NUMERIC,
    breakdown_strength_mv_m NUMERIC,
    extra                JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE materials_sma (
    material_id          INTEGER PRIMARY KEY REFERENCES materials(material_id) ON DELETE CASCADE,
    alloy_composition    TEXT NOT NULL,          -- e.g. "Ni50.8Ti49.2"
    transformation_t_c   NUMERIC,
    austenite_start_c    NUMERIC,
    austenite_finish_c   NUMERIC,
    martensite_start_c   NUMERIC,
    martensite_finish_c  NUMERIC,
    hysteresis_c         NUMERIC,
    training_method      TEXT,
    is_magnetic_sma      BOOLEAN DEFAULT FALSE,
    extra                JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE materials_piezo (
    material_id          INTEGER PRIMARY KEY REFERENCES materials(material_id) ON DELETE CASCADE,
    formula              TEXT,                   -- e.g. "Pb(Zr,Ti)O3"
    crystal_structure    TEXT,
    d33_pc_n             NUMERIC,                -- pC/N
    d31_pc_n             NUMERIC,
    k33                  NUMERIC,
    kt                   NUMERIC,
    curie_t_c            NUMERIC,
    poling_field_kv_mm   NUMERIC,
    is_single_crystal    BOOLEAN DEFAULT FALSE,
    extra                JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE materials_cnt (
    material_id          INTEGER PRIMARY KEY REFERENCES materials(material_id) ON DELETE CASCADE,
    cnt_type             TEXT,                   -- 'SWCNT' | 'MWCNT' | 'graphene' | 'rGO'
    diameter_nm          NUMERIC,
    length_mm            NUMERIC,
    twist_angle_deg      NUMERIC,
    coiling              BOOLEAN,                -- helically coiled yarn?
    infiltrant           TEXT,                   -- paraffin, silicone, etc.
    bias_voltage_v       NUMERIC,
    extra                JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE materials_biohybrid (
    material_id          INTEGER PRIMARY KEY REFERENCES materials(material_id) ON DELETE CASCADE,
    cell_type            TEXT,                   -- e.g. "cardiomyocyte", "C2C12"
    cell_source          TEXT,                   -- "primary rat", "iPSC-derived"
    scaffold_material    TEXT,                   -- "PDMS", "hydrogel", ...
    scaffold_geometry    TEXT,                   -- "cantilever", "ring", "pillar"
    culture_days         NUMERIC,
    is_optogenetic       BOOLEAN DEFAULT FALSE,
    stimulation_mode     TEXT,                   -- "electric", "optical", "chemical"
    extra                JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE materials_pneumatic (
    material_id          INTEGER PRIMARY KEY REFERENCES materials(material_id) ON DELETE CASCADE,
    geometry             TEXT,                   -- "McKibben", "bellows", "HASEL", "PneuNet"
    chamber_material     TEXT,
    reinforcement        TEXT,                   -- "fiber-reinforced", "unreinforced"
    working_fluid        TEXT,                   -- "air", "water", "hydraulic oil"
    max_pressure_kpa     NUMERIC,
    contraction_ratio    NUMERIC,
    extra                JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE materials_magnetic (
    material_id          INTEGER PRIMARY KEY REFERENCES materials(material_id) ON DELETE CASCADE,
    matrix_material      TEXT,                   -- "silicone", "PDMS"
    magnetic_filler      TEXT,                   -- "NdFeB", "Fe3O4", "carbonyl iron"
    filler_volume_fraction NUMERIC,
    remanence_mt         NUMERIC,
    applied_field_mt     NUMERIC,
    extra                JSONB NOT NULL DEFAULT '{}'
);

-- ----------------------------------------------------------------------------
-- Extraction audit — every LLM extraction run leaves a trail
-- ----------------------------------------------------------------------------

CREATE TABLE extraction_audit (
    audit_id             BIGSERIAL PRIMARY KEY,
    paper_id             INTEGER REFERENCES papers(paper_id) ON DELETE CASCADE,
    material_id          INTEGER REFERENCES materials(material_id) ON DELETE SET NULL,
    extractor_version    TEXT NOT NULL,           -- e.g. "muscle-extractor/0.1.0"
    model                TEXT NOT NULL,           -- e.g. "spark-1-pro"
    class_extractor      TEXT,                    -- e.g. "lce_v0", "sma_v0"
    prompt_hash          TEXT,                    -- sha256 of prompt template used
    raw_output           TEXT,                    -- raw model output
    parsed_json          JSONB,                   -- post-parse JSON
    validation_status    TEXT NOT NULL,           -- 'passed' | 'schema_fail' | 'value_warn' | 'rejected'
    validation_errors    TEXT[],
    validator_type       validator_type,
    validator_id         TEXT,                    -- username if human
    cost_usd             NUMERIC,
    tokens_in            INTEGER,
    tokens_out           INTEGER,
    duration_ms          INTEGER,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_paper        ON extraction_audit(paper_id);
CREATE INDEX idx_audit_material     ON extraction_audit(material_id);
CREATE INDEX idx_audit_created      ON extraction_audit(created_at DESC);
CREATE INDEX idx_audit_validation   ON extraction_audit(validation_status);

-- ----------------------------------------------------------------------------
-- Triggers: auto-update updated_at
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER papers_touch    BEFORE UPDATE ON papers     FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER materials_touch BEFORE UPDATE ON materials  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
