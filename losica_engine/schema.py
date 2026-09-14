"""Executable vocabulary and immutable compiled relation records."""
from dataclasses import dataclass

OUTPUT_SCHEMA_VERSION = "4.0"
DIAGNOSTICS_SCHEMA_VERSION = "4.0"

REGISTERED_PROCESS_TYPES = frozenset({"reduplication", "compound"})
PROPERTY_FIELDS = {
    "morphological_process": "value",
    "contains_any": "segments",
    "initial_any": "segments",
    "syllable_count": "values",
}

@dataclass(frozen=True)
class PremiseProvenance:
    status: str
    source: str
    def serialize(self): return {"status": self.status, "source": self.source}

@dataclass(frozen=True)
class StimulusPredicate:
    quantity_id: str
    unit: str
    operator: str
    value: float | None = None
    lower: float | None = None
    upper: float | None = None
    component_index: int | None = None
    def serialize(self):
        out={"quantity_id":self.quantity_id,"unit":self.unit,"operator":self.operator}
        if self.operator == "between": out.update(lower=self.lower, upper=self.upper)
        else: out["value"] = self.value
        if self.component_index is not None: out["component_index"] = self.component_index
        return out

@dataclass(frozen=True)
class CompiledCandidateProperty:
    type: str
    value: str | None = None
    segments: frozenset[str] = frozenset()
    values: frozenset[int] = frozenset()
    def serialize(self):
        if self.type == "morphological_process": return {"type": self.type, "value": self.value}
        if self.type in {"contains_any", "initial_any"}: return {"type": self.type, "segments": sorted(self.segments)}
        if self.type == "syllable_count": return {"type": self.type, "values": sorted(self.values)}
        raise ValueError(f"unknown compiled property type {self.type!r}")

@dataclass(frozen=True)
class RelationPremise:
    id: str
    stimulus_predicate: StimulusPredicate
    candidate_property: CompiledCandidateProperty
    provenance: PremiseProvenance
    def serialize(self):
        return {
            "relation_id": self.id,
            "stimulus_predicate": self.stimulus_predicate.serialize(),
            "candidate_property": self.candidate_property.serialize(),
            "premise_provenance": self.provenance.serialize(),
        }
