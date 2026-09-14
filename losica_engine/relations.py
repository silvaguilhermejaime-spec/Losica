from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
import math, operator as op

from .phonology import Root, root_segments
from .config import PhonologyConfig
from .schema import (
    REGISTERED_PROCESS_TYPES, PROPERTY_FIELDS, RelationPremise,
    CompiledCandidateProperty, PremiseProvenance, StimulusPredicate,
)
from .validation import (
    read_json, keys, require, identifier, label, provenance_text,
    MAX_RELATIONS, MAX_PROPERTY_ITEMS,
)

OPS={"lt":op.lt,"le":op.le,"gt":op.gt,"ge":op.ge,"eq":op.eq}

@dataclass(frozen=True)
class RelationMatch:
    relation_id: str
    predicate_count: int
    category_size: int
    match_type: str = "premise_instantiation"
    def serialize(self):
        return {
            "relation_id": self.relation_id,
            "match_type": self.match_type,
            "predicate_prevalence": {
                "predicate_count": self.predicate_count,
                "category_size": self.category_size,
                "fraction": f"{self.predicate_count}/{self.category_size}",
            },
        }

def _finite_number(x, context):
    require(type(x) in {int,float} and math.isfinite(x), f"{context}: finite number required")
    return float(x)

def compile_stimulus_predicate(relation_id, raw, measurement_catalog):
    require(isinstance(raw,dict), f"relation {relation_id!r}: stimulus_predicate is required")
    typ=raw.get("operator")
    require(typ in set(OPS)|{"between"}, f"relation {relation_id!r}: predicate operator outside registered set {typ!r}")
    required={"quantity_id","unit","operator"}|({"lower","upper"} if typ=="between" else {"value"})
    keys(raw,required,{"component_index"},context=f"relation {relation_id!r} stimulus_predicate")
    qid=identifier(raw["quantity_id"],"predicate quantity_id")
    require(qid in measurement_catalog, f"relation {relation_id!r}: quantity_id {qid!r} is outside the loaded measurement catalog")
    unit=label(raw["unit"],"predicate unit")
    require(unit==measurement_catalog[qid], f"relation {relation_id!r}: unit {unit!r} differs from loaded measurement unit {measurement_catalog[qid]!r} for {qid!r}")
    ci=raw.get("component_index")
    if ci is not None:
        require(type(ci) is int and ci>=0, f"relation {relation_id!r}: component_index must be a non-negative integer")
    if typ=="between":
        lo=_finite_number(raw["lower"],"predicate lower"); hi=_finite_number(raw["upper"],"predicate upper")
        require(lo<=hi, f"relation {relation_id!r}: predicate lower must be <= upper")
        return StimulusPredicate(qid,unit,typ,lower=lo,upper=hi,component_index=ci)
    return StimulusPredicate(qid,unit,typ,value=_finite_number(raw["value"],"predicate value"),component_index=ci)

def load_relations(path: str | Path, cfg: PhonologyConfig, measurement_catalog: dict[str,str]) -> tuple[RelationPremise,...]:
    data=read_json(path); keys(data,{"relations"},context="relations"); relations=data["relations"]
    require(isinstance(relations,list),"relations must be a list")
    require(len(relations)<=MAX_RELATIONS,f"relations: at most {MAX_RELATIONS} entries supported")
    out=[];seen=set()
    for relation in relations:
        keys(relation,{"id","stimulus_predicate","candidate_property","provenance"},context="relation")
        rid=identifier(relation["id"],"relation id"); require(rid not in seen,f"duplicate relation id {rid!r}");seen.add(rid)
        predicate=compile_stimulus_predicate(rid,relation["stimulus_predicate"],measurement_catalog)
        prop=compile_candidate_property(rid,relation["candidate_property"],cfg)
        provenance=relation["provenance"]; keys(provenance,{"status","source"},context=f"relation {rid!r} premise provenance")
        prov=PremiseProvenance(status=label(provenance["status"],"premise status"),source=provenance_text(provenance["source"],"premise source"))
        out.append(RelationPremise(rid,predicate,prop,prov))
    return tuple(out)

def compile_candidate_property(relation_id: str, prop: dict, cfg: PhonologyConfig) -> CompiledCandidateProperty:
    require(isinstance(prop,dict),f"relation {relation_id!r}: candidate_property is required")
    typ=prop.get("type"); require(isinstance(typ,str) and typ in PROPERTY_FIELDS,f"relation {relation_id!r}: unknown candidate_property type {typ!r}")
    field=PROPERTY_FIELDS[typ]; keys(prop,{"type",field},context="candidate_property")
    if typ=="morphological_process":
        value=label(prop.get("value"),"morphological_process value")
        require(value in REGISTERED_PROCESS_TYPES,f"relation {relation_id!r}: morphological_process value {value!r} is outside the registered process-type vocabulary")
        return CompiledCandidateProperty(type=typ,value=value)
    if typ in {"contains_any","initial_any"}:
        segments=prop.get("segments"); require(isinstance(segments,list) and bool(segments),f"relation {relation_id!r}: {typ} requires segments")
        require(len(segments)<=MAX_PROPERTY_ITEMS,f"relation {relation_id!r}: {typ} supports at most {MAX_PROPERTY_ITEMS} segments")
        inventory=set(cfg.consonants)|set(cfg.vowels); normalized=[]
        for segment in segments:
            require(isinstance(segment,str) and segment in inventory,f"relation {relation_id!r}: segment {segment!r} is outside the Pre-Proto inventory"); normalized.append(segment)
        return CompiledCandidateProperty(type=typ,segments=frozenset(normalized))
    if typ=="syllable_count":
        values=prop.get("values"); require(isinstance(values,list) and bool(values),f"relation {relation_id!r}: syllable_count requires positive integers")
        require(len(values)<=MAX_PROPERTY_ITEMS,f"relation {relation_id!r}: syllable_count supports at most {MAX_PROPERTY_ITEMS} values")
        require(all(type(x) is int and x>=1 for x in values),f"relation {relation_id!r}: syllable_count requires positive integers")
        return CompiledCandidateProperty(type=typ,values=frozenset(values))
    raise ValueError(f"relation {relation_id!r}: unknown candidate_property type {typ!r}")

def _measurement_scalar(stimulus,predicate):
    measurement=stimulus.get("measurements",{}).get(predicate.quantity_id)
    if measurement is None or measurement.get("unit") != predicate.unit: return None
    value=measurement.get("value")
    if isinstance(value,tuple):
        if predicate.component_index is None or predicate.component_index>=len(value): return None
        value=value[predicate.component_index]
    elif predicate.component_index is not None:
        return None
    return value

def predicate_matches(stimulus,predicate):
    value=_measurement_scalar(stimulus,predicate)
    if value is None: return False
    if predicate.operator=="between": return predicate.lower <= value <= predicate.upper
    return OPS[predicate.operator](value,predicate.value)

@dataclass(frozen=True)
class CategoryPredicateCounts:
    counts: MappingProxyType
    size: int
    @classmethod
    def from_members(cls,members,relations):
        counts={r.id:sum(predicate_matches(member,r.stimulus_predicate) for member in members) for r in relations}
        return cls(MappingProxyType(counts),len(members))

def predicate_prevalence(stimuli, relation: RelationPremise):
    if isinstance(stimuli,CategoryPredicateCounts): return stimuli.counts.get(relation.id,0),stimuli.size
    return sum(predicate_matches(s,relation.stimulus_predicate) for s in stimuli),len(stimuli)

@dataclass(frozen=True)
class CandidateFeatures:
    segments: frozenset[str]
    initial: str
    syllable_count: int
    morphological_process: str|None

def candidate_features(root,cfg,morphological_process):
    segments=root_segments(root,cfg)
    return CandidateFeatures(frozenset(segments),segments[0] if segments else "",root.syllable_count,morphological_process)

def compiled_property_matches(features,prop):
    if prop.type=="morphological_process": return features.morphological_process==prop.value
    if prop.type=="contains_any": return not prop.segments.isdisjoint(features.segments)
    if prop.type=="initial_any": return features.initial in prop.segments
    if prop.type=="syllable_count": return features.syllable_count in prop.values
    raise ValueError(f"unknown candidate_property type {prop.type!r}")

def candidate_property_matches(root,cfg,prop,*,morphological_process=None):
    compiled=prop if isinstance(prop,CompiledCandidateProperty) else compile_candidate_property("ad hoc",prop,cfg)
    return compiled_property_matches(candidate_features(root,cfg,morphological_process),compiled)

def matched_relations(root,cfg,stimuli,relations,*,morphological_process=None):
    features=candidate_features(root,cfg,morphological_process); out=[]
    for relation in relations:
        if not compiled_property_matches(features,relation.candidate_property): continue
        count,total=predicate_prevalence(stimuli,relation)
        if count: out.append(RelationMatch(relation.id,count,total))
    return tuple(out)
