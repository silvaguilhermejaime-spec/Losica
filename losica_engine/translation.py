"""English adapter for a generated Losica snapshot.

The adapter maps English surface forms to language-neutral semantic structures.
It evaluates source-language queries against an immutable generated-language snapshot.
"""
from __future__ import annotations

import re

from .grammar_v021 import LanguageExecutor, clause, entity, participant_reference


def _normalize_word(word: str) -> str:
    word = word.lower()
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and len(word) > 3:
        return word[:-1]
    return word


def _english_index(state: dict) -> dict[str, str]:
    index: dict[str, str] = {}
    for row in state["lexicon"]:
        label = row.get("display", {}).get("en")
        if label:
            index[_normalize_word(label)] = row["concept"]
        for alias in row.get("display", {}).get("en_aliases", []):
            index[_normalize_word(alias.replace(" (24 hours)", "").replace(" (soil)", ""))] = row["concept"]
    return index


def _pronoun(word: str) -> dict | None:
    if word == "i":
        return participant_reference(speaker="required", addressee="forbidden", cardinality=1)
    if word == "you":
        # English second-person reference leaves number open. The controlled-source
        # adapter selects singular; richer adapters can preserve the full ambiguity.
        return participant_reference(speaker="forbidden", addressee="required", cardinality=1)
    if word in {"he", "she", "it"}:
        return participant_reference(speaker="forbidden", addressee="forbidden", cardinality=1)
    if word == "we":
        return participant_reference(speaker="required", addressee="unknown", minimum=2)
    if word == "they":
        return participant_reference(speaker="forbidden", addressee="forbidden", minimum=2)
    return None


def _lookup(index: dict[str, str], word: str, *, role: str) -> str:
    normalized = _normalize_word(word)
    if normalized in index:
        return index[normalized]
    raise KeyError(f"English adapter source_lookup=empty role={role} source={word!r}")


def parse_controlled_source(state: dict, text: str) -> dict:
    words = re.findall(r"[A-Za-z]+", text.lower())
    question = text.rstrip().endswith("?")
    while words and words[0] in {"the", "a", "an"}:
        words.pop(0)
    tense, polarity = "NPST", "POS"
    if words and words[0] in {"did", "does", "do"}:
        tense = "PST" if words.pop(0) == "did" else "NPST"
        question = True
    if len(words) < 2:
        raise ValueError("controlled source requires at least a predicate and one argument")

    index = _english_index(state)
    subject_word = words.pop(0)
    subject = _pronoun(subject_word)
    if subject is None:
        subject = entity(_lookup(index, subject_word, role="subject"))

    if words and words[0] == "does":
        words.pop(0)
    if words and words[0] == "not":
        words.pop(0)
        polarity = "NEG"

    predicate_word = words.pop(0)
    predicate = _lookup(index, predicate_word, role="predicate")
    object_words = [w for w in words if w not in {"the", "a", "an", "to"}]
    arguments = {"AGENT": subject}
    if object_words:
        p = _pronoun(object_words[0])
        arguments["PATIENT"] = p if p is not None else entity(_lookup(index, object_words[0], role="object"))
    if len(object_words) > 1:
        r = _pronoun(object_words[1])
        arguments["RECIPIENT"] = r if r is not None else entity(_lookup(index, object_words[1], role="recipient"))
    return clause(predicate, arguments, features={"tense": tense, "polarity": polarity, **({"question": "polar"} if question else {})})


def translate(state: dict, source: dict | str) -> dict:
    graph = source if isinstance(source, dict) else parse_controlled_source(state, source)
    executor = LanguageExecutor(lexicon=state["lexicon"], paradigms=state["paradigms"], morphology=state["morphology"], profile=state["profile"])
    result = executor.realize(graph)
    result["source"] = source
    result["lexical_state_mutated"] = False
    return result
