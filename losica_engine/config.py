"""Finite configuration language for phonology and historical derivation."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
from .validation import keys, require, text, strings, read_json, label

SYLLABLE_MODELS = frozenset({"(C)V(C)"})
PROSODY_MODELS = frozenset({"exactly_one_syllable"})
LENITION_ENVIRONMENTS = frozenset({"coda", "intervocalic"})
GLIDE_CONDITIONS = frozenset({"nonprominent_adjacent_vowel"})
LOWERING_CONDITIONS = frozenset({"nonprominent_syllabic"})

@dataclass(frozen=True)
class PhonologyConfig:
    consonants: tuple[str, ...]
    vowels: tuple[str, ...]
    onsets: tuple[str, ...]
    codas: tuple[str, ...]
    syllable: str
    lexical_prominence: str = "exactly_one_syllable"
    language_metadata: str = ""
    @property
    def legal_syllable_count(self):
        return len(self.onsets) * len(self.vowels) * len(self.codas)

@dataclass(frozen=True)
class TransitionConfig:
    postnasal: Mapping[str, str]
    p_segment: str
    p_result: str
    p_environments: tuple[str, ...]
    glides_enabled: bool
    glides: Mapping[str, str]
    glide_condition: str
    coalescence: Mapping[str, str]
    vowel_lowering_enabled: bool
    vowel_lowering: Mapping[str, str]
    vowel_lowering_condition: str
    name_metadata: str = ""

def segment(value, context):
    text(value, context)
    require(len(value) <= 8 and not any(c in value for c in ".ˈ|"),
            f"{context}: segment must use at most 8 characters and lexical segment notation")
    return value

def load_phonology(path):
    d = read_json(path)
    keys(d, {"phonology", "prosody"}, {"language"}, "phonology configuration")
    p = d["phonology"]
    keys(p, {"consonants", "vowels", "onsets", "codas", "syllable"}, context="phonology")
    keys(d["prosody"], {"lexical_prominence"}, context="prosody")
    require(p["syllable"] in SYLLABLE_MODELS, f"phonology.syllable must be one of {sorted(SYLLABLE_MODELS)}")
    require(d["prosody"]["lexical_prominence"] in PROSODY_MODELS, f"lexical_prominence must be one of {sorted(PROSODY_MODELS)}")
    inv = {}
    for name in ("consonants", "vowels", "onsets", "codas"):
        values = strings(p[name], name, empty=name in {"onsets", "codas"})
        require(0 < len(values) <= 64, f"{name}: inventory size must be 1..64")
        for s in values:
            if s:
                segment(s, name)
        inv[name] = values
    require(not set(inv["consonants"]) & set(inv["vowels"]), "consonants and vowels must be disjoint")
    for name in ("onsets", "codas"):
        require(set(inv[name]) <= set(inv["consonants"]) | {""}, f"{name}: outside consonant inventory")
    cfg = PhonologyConfig(**inv, syllable=p["syllable"],
        lexical_prominence=d["prosody"]["lexical_prominence"],
        language_metadata=label(d["language"], "language") if "language" in d else "")
    require(cfg.legal_syllable_count <= 4096, "legal syllable inventory exceeds 4096")
    from .phonology import tokenize_surface
    seen = set()
    for o in cfg.onsets:
        for v in cfg.vowels:
            for c in cfg.codas:
                surface = o + v + c
                require(surface not in seen, "ambiguous legal syllable encoding")
                seen.add(surface)
                require(tokenize_surface(surface, cfg.consonants, cfg.vowels) ==
                        tuple(x for x in (o, v, c) if x), f"ambiguous segment tokenization: {surface!r}")
    return cfg

def mapping(value, context):
    require(isinstance(value, dict), f"{context}: mapping required")
    require(len(value) <= 64, f"{context}: at most 64 mappings supported")
    for k, v in value.items():
        segment(k, context)
        segment(v, context)
    return MappingProxyType(dict(value))

def load_transition(path):
    d = read_json(path)
    keys(d, {"postnasal", "p_lenition", "glides", "coalescence", "vowel_lowering"}, {"name"}, "transition")
    p, g, v = d["p_lenition"], d["glides"], d["vowel_lowering"]
    keys(p, {"segment", "result", "environments"}, context="p_lenition")
    env = strings(p["environments"], "lenition environments")
    require(set(env) <= LENITION_ENVIRONMENTS, f"lenition environments must be within {sorted(LENITION_ENVIRONMENTS)}")
    for b, conditions, name in ((g, GLIDE_CONDITIONS, "glide"), (v, LOWERING_CONDITIONS, "vowel-lowering")):
        require(isinstance(b, dict) and "condition" in b and "enabled" in b, f"{name}: enabled and condition required")
        require(type(b["enabled"]) is bool, f"{name}: enabled must be boolean")
        require(b["condition"] in conditions, f"{name} condition must be one of {sorted(conditions)}")
    return TransitionConfig(mapping(d["postnasal"], "postnasal"), segment(p["segment"], "lenition segment"),
        segment(p["result"], "lenition result"), env, g["enabled"],
        mapping({k:x for k,x in g.items() if k not in {"enabled","condition"}}, "glides"), g["condition"],
        mapping(d["coalescence"], "coalescence"), v["enabled"],
        mapping({k:x for k,x in v.items() if k not in {"enabled","condition"}}, "lowering"), v["condition"],
        label(d["name"], "name") if "name" in d else "")

def validate_transition(cfg, tr):
    c, v = set(cfg.consonants), set(cfg.vowels)
    require(tr.p_segment in c, "lenition segment outside input consonants")
    require(set(tr.glides) <= v, "glide sources outside input vowels")
    require(set(tr.vowel_lowering) <= v, "lowering sources outside input vowels")
    consonants = c | {tr.p_result} | set(tr.postnasal.values()) | set(tr.coalescence.values())
    glides = set(tr.glides.values())
    vowels = v | set(tr.vowel_lowering.values())
    require(not (consonants & vowels or glides & vowels or glides & consonants), "historical segment kinds must be disjoint")
    for key in tr.postnasal:
        pairs = [(a,b) for a in consonants for b in consonants if a+b == key]
        require(len(pairs) == 1 and pairs[0][0] in {"m","n"},
                f"postnasal key {key!r}: unique nasal+consonant pair required (nasals: m,n)")
    for key in tr.coalescence:
        require(sum(a+b == key for a in consonants for b in glides) == 1,
                f"coalescence key {key!r}: unique consonant+glide pair required")
