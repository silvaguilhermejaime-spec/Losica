"""Executable Losica morpheme composition.

Morpheme sequence → segment sequence → morpheme-internal syllabification →
boundary morphophonology → resyllabification → prominence → orthography.
Every operation is retained in the returned trace.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .config import PhonologyConfig
from .phonology import syllabify_surface, tokenize_surface


@dataclass(frozen=True)
class Morpheme:
    morpheme_id: str
    form: str
    gloss: str
    attachment: str = "root"


def _segments(text: str, cfg: PhonologyConfig) -> list[str]:
    return list(tokenize_surface(text.replace(".", ""), cfg.consonants, cfg.vowels))


def _repair(tokens: list[str], cfg: PhonologyConfig, rules: dict) -> tuple[list[str], list[dict]]:
    """Apply licensed general rules uniformly across eligible forms."""
    out = list(tokens)
    operations: list[dict] = []
    vowels, consonants = set(cfg.vowels), set(cfg.consonants)

    # Identical-vowel fusion is a boundary-general rule.
    if rules.get("identical_vowel_fusion", True):
        i = 1
        while i < len(out):
            if out[i] == out[i - 1] and out[i] in vowels:
                operations.append({"rule": "MPH-FUSION-01", "operation": "fusion", "input": out[i - 1:i + 1], "output": [out[i]], "position": i - 1})
                del out[i]
            else:
                i += 1

    # /n/ takes the available labial nasal feature before /p/.
    if rules.get("nasal_place_assimilation", True):
        for i in range(len(out) - 1):
            if out[i:i + 2] == ["n", "p"]:
                operations.append({"rule": "MPH-ASSIM-01", "operation": "assimilation", "input": ["n", "p"], "output": ["m", "p"], "position": i})
                out[i] = "m"

    # The active (C)V(C) grammar permits single-segment margins. Insert the
    # least-marked vowel between adjacent consonants, including initial /rt,
    # /rk/ and word-final /kn/ boundaries.
    epenthetic = rules.get("epenthetic_vowel", "a")
    if epenthetic not in vowels:
        raise ValueError(f"epenthetic vowel {epenthetic!r} is outside the active Losica inventory")
    i = 1
    while i < len(out):
        if out[i - 1] in consonants and out[i] in consonants:
            operations.append({"rule": "MPH-EPENTHESIS-01", "operation": "epenthesis", "input": out[i - 1:i + 1], "output": [out[i - 1], epenthetic, out[i]], "position": i})
            out.insert(i, epenthetic)
            i += 2
        else:
            i += 1

    if not any(x in vowels for x in out):
        repaired = []
        for token in out:
            repaired.extend([token, epenthetic])
        operations.append({"rule": "MPH-EPENTHESIS-02", "operation": "epenthesis", "input": out, "output": repaired, "position": 0})
        out = repaired
    return out, operations


def prominence_index(syllables: list[str] | tuple[str, ...], rule: str) -> int:
    if not syllables:
        raise ValueError("prosody requires at least one syllable")
    if rule == "initial":
        return 0
    if rule == "final":
        return len(syllables) - 1
    if rule == "penultimate":
        return max(0, len(syllables) - 2)
    raise ValueError(f"unknown prominence rule {rule!r}")


def orthographic_form(phonemic: str, mapping: dict[str, str], cfg: PhonologyConfig) -> str:
    tokens = tokenize_surface(phonemic.replace(".", ""), cfg.consonants, cfg.vowels)
    return "".join(mapping[x] for x in tokens)


def phonemic_from_orthography(text: str, mapping: dict[str, str], cfg: PhonologyConfig) -> str:
    reverse = {v: k for k, v in mapping.items()}
    if len(reverse) != len(mapping) or "" in reverse:
        raise ValueError("orthography must be a non-empty one-to-one segment mapping")
    graphemes = sorted(reverse, key=lambda x: (-len(x), x))
    tokens, i = [], 0
    while i < len(text):
        for g in graphemes:
            if text.startswith(g, i):
                tokens.append(reverse[g])
                i += len(g)
                break
        else:
            raise ValueError(f"orthographic parsing stopped at offset {i} in {text!r}")
    return ".".join(syllabify_surface("".join(tokens), cfg))


def realize_morphemes(
    morphemes: Iterable[Morpheme | dict],
    cfg: PhonologyConfig,
    *,
    rules: dict | None = None,
    prominence_rule: str = "penultimate",
    orthography: dict[str, str] | None = None,
) -> dict:
    """Realize a morpheme sequence and return every representation boundary."""
    normalized = []
    for item in morphemes:
        if isinstance(item, Morpheme):
            normalized.append(item)
        else:
            normalized.append(Morpheme(
                str(item["morpheme_id"]), str(item.get("form", "")), str(item.get("gloss", "")), str(item.get("attachment", "root"))
            ))
    if not normalized or not any(m.form for m in normalized):
        raise ValueError("morpheme composition requires at least one non-empty form")
    raw = "".join(m.form.replace(".", "") for m in normalized)
    tokens = _segments(raw, cfg)
    internal_syllabifications = []
    for morpheme in normalized:
        try:
            parsed = list(syllabify_surface(morpheme.form.replace(".", ""), cfg)) if morpheme.form else []
            internal_syllabifications.append({"morpheme_id": morpheme.morpheme_id, "licensed": True, "syllables": parsed})
        except ValueError:
            internal_syllabifications.append({"morpheme_id": morpheme.morpheme_id, "licensed": False, "syllables": None, "repair_domain": "morpheme boundary composition"})
    repaired, operations = _repair(tokens, cfg, rules or {})
    syllables = list(syllabify_surface("".join(repaired), cfg))
    prominence = prominence_index(syllables, prominence_rule)
    phonemic = ".".join(syllables)
    mapping = orthography or {x: x for x in (*cfg.consonants, *cfg.vowels)}
    spelling = orthographic_form(phonemic, mapping, cfg)
    return {
        "morpheme_sequence": [m.__dict__ for m in normalized],
        "morpheme_glosses": [m.gloss for m in normalized if m.form],
        "underlying_form": raw,
        "segment_sequence": tokens,
        "initial_syllabification": internal_syllabifications,
        "operations": operations + [{"rule": "MPH-RESYLLABIFY-01", "operation": "resyllabification", "output": syllables}],
        "syllables": syllables,
        "prominence": prominence,
        "prominent_syllable": syllables[prominence],
        "annotated_phonemic": ".".join(("ˈ" if i == prominence else "") + s for i, s in enumerate(syllables)),
        "annotated_form": ".".join(("ˈ" if i == prominence else "") + s for i, s in enumerate(syllables)),
        "phonemic": phonemic,
        "surface_phonemic": phonemic,
        "surface_form": phonemic,
        "orthographic": spelling,
    }
