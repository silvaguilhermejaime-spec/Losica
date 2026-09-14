"""Language-neutral semantic identifiers used by the complete-language generator."""
from __future__ import annotations

import re

# Stable grammatical-semantic IDs. These identify Losica's formal semantic operators.
G_DEM_PROX = "g:0101"
G_DEM_DIST = "g:0102"
G_NUM_1 = "n:1"
G_NUM_2 = "n:2"
G_INT_PERSON = "g:0301"
G_INT_THING = "g:0302"
G_INT_PLACE = "g:0303"
G_QUANT_UNIV = "g:0401"
G_QUANT_EXIST = "g:0402"
G_COORD_ADD = "g:0501"
G_COORD_ALT = "g:0502"
G_Q_POLAR = "g:0601"
G_NEG = "g:0602"
G_COMP = "g:0603"
G_REL = "g:0604"
G_IMP = "g:0605"
G_COP = "g:0701"
G_EXIST = "g:0702"
G_ADP_LOC = "g:0801"
G_ADP_SOURCE = "g:0802"
G_ADP_INSTR = "g:0803"

FUNCTION_SPECS = [
    (G_DEM_PROX, "demonstrative", {"deixis": "PROX"}, None),
    (G_DEM_DIST, "demonstrative", {"deixis": "DIST"}, None),
    (G_INT_PERSON, "interrogative", {"semantic_type": "person"}, None),
    (G_INT_THING, "interrogative", {"semantic_type": "thing"}, None),
    (G_INT_PLACE, "interrogative", {"semantic_type": "place"}, None),
    (G_QUANT_UNIV, "quantifier", {"quantification": "UNIVERSAL"}, None),
    (G_QUANT_EXIST, "quantifier", {"quantification": "EXISTENTIAL"}, None),
    (G_COORD_ADD, "conjunction", {"relation": "coordination"}, None),
    (G_COORD_ALT, "conjunction", {"relation": "alternative"}, None),
    (G_Q_POLAR, "particle", {"function": "polar_question"}, None),
    (G_NEG, "particle", {"function": "negation"}, None),
    (G_COMP, "complementizer", {"function": "complement_clause"}, None),
    (G_REL, "particle", {"function": "relative_clause"}, None),
    (G_IMP, "particle", {"function": "imperative"}, None),
    (G_COP, "auxiliary", {"function": "copular"}, {"frame_id": "f:theme1", "valency": 1, "roles": ["THEME"], "required_roles": ["THEME"], "role_alternatives": [], "alternations": []}),
    (G_EXIST, "verb", {"function": "existential"}, {"frame_id": "f:theme1", "valency": 1, "roles": ["THEME"], "required_roles": ["THEME"], "role_alternatives": [], "alternations": []}),
    (G_ADP_LOC, "adposition", {"case_role": "LOC"}, None),
    (G_ADP_SOURCE, "adposition", {"case_role": "SOURCE"}, None),
    (G_ADP_INSTR, "adposition", {"case_role": "INSTRUMENT"}, None),
]

# These are Losica-internal candidate lexical frames. Generation samples among them
# after semantic regions have been formed.
LEXICAL_FRAME_SPECS = {
    "f:theme1": {"valency": 1, "roles": ["THEME"], "required_roles": ["THEME"], "role_alternatives": [["AGENT"]], "alternations": ["CAUS"]},
    "f:agent1": {"valency": 1, "roles": ["AGENT"], "required_roles": ["AGENT"], "role_alternatives": [["THEME"]], "alternations": ["CAUS"]},
    "f:patient2": {"valency": 2, "roles": ["AGENT", "PATIENT"], "required_roles": ["AGENT", "PATIENT"], "role_alternatives": [], "alternations": ["CAUS", "PASS", "ANTIP"]},
    "f:transfer3": {"valency": 3, "roles": ["AGENT", "PATIENT", "RECIPIENT"], "required_roles": ["AGENT", "PATIENT", "RECIPIENT"], "role_alternatives": [], "alternations": ["APPL", "PASS"]},
    "f:content2": {"valency": 2, "roles": ["AGENT", "CONTENT"], "required_roles": ["AGENT", "CONTENT"], "role_alternatives": [], "alternations": ["CAUS"]},
}


def probe_id(concepticon_id: str) -> str:
    return f"c:{concepticon_id}"


def concepticon_id(probe: str) -> str | None:
    return probe[2:] if isinstance(probe, str) and probe.startswith("c:") else None


def frame_structure(frame_id: str) -> dict:
    spec = LEXICAL_FRAME_SPECS[frame_id]
    return {"frame_id": frame_id, **{k: (list(v) if isinstance(v, list) else v) for k, v in spec.items()}}


def _identifier(prefix: str, value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    if not text:
        raise ValueError(f"{prefix} identifier requires a non-empty value")
    return f"{prefix}:{text}"


def lexical_item_id(value: object) -> str:
    return _identifier("lx", value)


def meaning_region_id(value: object) -> str:
    return _identifier("sr", value)


def meaning_partition_id(value: object) -> str:
    return _identifier("sp", value)


def meaning_cell_id(value: object) -> str:
    return _identifier("sc", value)


def concepticon_link(object_id: object) -> dict[str, str]:
    return {"namespace": "concepticon", "object_id": str(object_id)}
