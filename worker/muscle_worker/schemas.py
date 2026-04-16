"""Pydantic schemas mirroring the database. These double as the LLM-extraction output contract:
the extractor produces JSON that validates against these models, and only then touches Postgres."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Stimulus(str, Enum):
    electric_field = "electric_field"
    electric_current = "electric_current"
    thermal = "thermal"
    optical = "optical"
    chemical_ph = "chemical_ph"
    chemical_solvent = "chemical_solvent"
    humidity = "humidity"
    magnetic = "magnetic"
    pneumatic = "pneumatic"
    mechanical = "mechanical"
    combustion = "combustion"
    multi = "multi"
    unknown = "unknown"


# ---------------------------------------------------------------------------
# Universal performance metrics (every row has these)
# ---------------------------------------------------------------------------

class UniversalMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_slug: str = Field(..., description="Top-level taxonomy slug, e.g. 'lce' or 'niti'.")
    subclass_slug: Optional[str] = None

    material_name: Optional[str] = None
    material_aliases: list[str] = Field(default_factory=list)

    stimulus: Stimulus = Stimulus.unknown
    drive_magnitude_value: Optional[float] = None
    drive_magnitude_unit: Optional[str] = None

    actuation_strain_pct: Optional[float] = Field(None, ge=0, le=1000)
    blocking_stress_kpa: Optional[float] = Field(None, ge=0)
    work_density_kj_m3: Optional[float] = Field(None, ge=0)
    power_density_w_kg: Optional[float] = Field(None, ge=0)
    response_time_s: Optional[float] = Field(None, ge=0)
    cycle_life: Optional[int] = Field(None, ge=0)
    efficiency_pct: Optional[float] = Field(None, ge=0, le=100)
    operating_t_min_c: Optional[float] = None
    operating_t_max_c: Optional[float] = None
    youngs_modulus_mpa: Optional[float] = Field(None, ge=0)
    trl: Optional[int] = Field(None, ge=1, le=9)

    notes: Optional[str] = None
    extraction_confidence: float = Field(..., ge=0, le=1)


# ---------------------------------------------------------------------------
# Per-class extensions
# ---------------------------------------------------------------------------

class PolymerExtension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    backbone_smiles: Optional[str] = None
    mesogen_smiles: Optional[str] = None
    crosslinker_smiles: Optional[str] = None
    spacer_smiles: Optional[str] = None
    endcap_smiles: Optional[str] = None
    dopant_smiles: Optional[str] = None
    mol_pct_crosslinker: Optional[float] = None
    mol_pct_mesogen: Optional[float] = None
    glass_transition_c: Optional[float] = None
    nematic_iso_c: Optional[float] = None
    mn_g_mol: Optional[float] = None
    mw_g_mol: Optional[float] = None
    pdi: Optional[float] = None
    crosslink_density: Optional[float] = None
    dielectric_constant: Optional[float] = None
    breakdown_strength_mv_m: Optional[float] = None


class SMAExtension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alloy_composition: str
    transformation_t_c: Optional[float] = None
    austenite_start_c: Optional[float] = None
    austenite_finish_c: Optional[float] = None
    martensite_start_c: Optional[float] = None
    martensite_finish_c: Optional[float] = None
    hysteresis_c: Optional[float] = None
    training_method: Optional[str] = None
    is_magnetic_sma: bool = False


class PiezoExtension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    formula: Optional[str] = None
    crystal_structure: Optional[str] = None
    d33_pc_n: Optional[float] = None
    d31_pc_n: Optional[float] = None
    k33: Optional[float] = None
    kt: Optional[float] = None
    curie_t_c: Optional[float] = None
    poling_field_kv_mm: Optional[float] = None
    is_single_crystal: bool = False


class CNTExtension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cnt_type: Optional[str] = None
    diameter_nm: Optional[float] = None
    length_mm: Optional[float] = None
    twist_angle_deg: Optional[float] = None
    coiling: Optional[bool] = None
    infiltrant: Optional[str] = None
    bias_voltage_v: Optional[float] = None


class BiohybridExtension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cell_type: Optional[str] = None
    cell_source: Optional[str] = None
    scaffold_material: Optional[str] = None
    scaffold_geometry: Optional[str] = None
    culture_days: Optional[float] = None
    is_optogenetic: bool = False
    stimulation_mode: Optional[str] = None


class PneumaticExtension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    geometry: Optional[str] = None
    chamber_material: Optional[str] = None
    reinforcement: Optional[str] = None
    working_fluid: Optional[str] = None
    max_pressure_kpa: Optional[float] = None
    contraction_ratio: Optional[float] = None


class MagneticExtension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matrix_material: Optional[str] = None
    magnetic_filler: Optional[str] = None
    filler_volume_fraction: Optional[float] = None
    remanence_mt: Optional[float] = None
    applied_field_mt: Optional[float] = None


# Polymer extension covers 4 classes that share the polymer schema.
POLYMER_CLASSES = {"electronic_eap", "ionic_eap", "thermal_polymer", "gel"}

CLASS_EXTENSION_MAP = {
    "electronic_eap": PolymerExtension,
    "ionic_eap": PolymerExtension,
    "thermal_polymer": PolymerExtension,
    "gel": PolymerExtension,
    "sma": SMAExtension,
    "piezo": PiezoExtension,
    "carbon": CNTExtension,
    "biohybrid": BiohybridExtension,
    "pneumatic": PneumaticExtension,
    "magnetic": MagneticExtension,
    "combustion": None,  # no extension table for now
}


class MaterialExtraction(BaseModel):
    """Top-level container for one extracted material row."""

    model_config = ConfigDict(extra="forbid")

    universal: UniversalMetrics
    polymer: Optional[PolymerExtension] = None
    sma: Optional[SMAExtension] = None
    piezo: Optional[PiezoExtension] = None
    cnt: Optional[CNTExtension] = None
    biohybrid: Optional[BiohybridExtension] = None
    pneumatic: Optional[PneumaticExtension] = None
    magnetic: Optional[MagneticExtension] = None

    def validate_extension_matches_class(self) -> list[str]:
        """Return a list of validation error strings if the wrong extension is populated for the class."""
        cls_slug = self.universal.class_slug
        expected = CLASS_EXTENSION_MAP.get(cls_slug)
        errs: list[str] = []

        populated = [
            ("polymer", self.polymer),
            ("sma", self.sma),
            ("piezo", self.piezo),
            ("cnt", self.cnt),
            ("biohybrid", self.biohybrid),
            ("pneumatic", self.pneumatic),
            ("magnetic", self.magnetic),
        ]

        if expected is None:
            # Class has no extension; nothing should be populated.
            for name, val in populated:
                if val is not None:
                    errs.append(f"class '{cls_slug}' has no extension table but '{name}' was populated")
            return errs

        for name, val in populated:
            if val is not None and not isinstance(val, expected):
                errs.append(f"class '{cls_slug}' expected {expected.__name__} but got {type(val).__name__} in '{name}'")

        return errs


# ---------------------------------------------------------------------------
# Paper-level ingest schema (what the crawl step emits)
# ---------------------------------------------------------------------------

class PaperRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    abstract: Optional[str] = None
    full_text_md: Optional[str] = None
    primary_class_slug: Optional[str] = None
    seed_source: str = "hand_seed"
