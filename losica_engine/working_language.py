"""Compact, source-backed, executable Losica working-language layer.

Concepticon IDs supply the semantic inventory.  English glosses are display and
input-adapter data only: form allocation depends solely on the seed and numeric
semantic IDs.  The grammar is a compact SOV interlingua with overt role/TAM
particles, so it can be used without shipping precomputed paradigm tables.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import re
import unicodedata

from .config import load_phonology
from .morphophonology import orthographic_form
from .phonology import generate_roots, is_legal_surface, legal_syllables
from .possession_kinship import load_possession_kinship, nominal_sequence


SCHEMA = "losica-working-language/1"
DEFAULT_SEED = 19020
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "data" / "concepticon_inventory_v0_30.json"
DEFAULT_PHONOLOGY = ROOT / "config" / "preproto.json"
DEFAULT_POSSESSION_KINSHIP = ROOT / "config" / "possession_kinship.json"

MARKER_SPECS = (
    ("ref:utterer", "reference", "current utterance source"),
    ("ref:interlocutor", "reference", "current utterance target"),
    ("ref:context", "reference", "contextually identified referent"),
    ("ref:utterer-set", "reference", "group associated with the current utterance source"),
    ("ref:context-set", "reference", "contextually identified group"),
    ("role:acc", "role", "patient"),
    ("role:dat", "role", "recipient or beneficiary"),
    ("role:loc", "role", "location or time"),
    ("tam:pst", "tense", "past"),
    ("asp:pros", "aspect", "prospective: approaching, intended, or expected event"),
    ("asp:pfv", "aspect", "perfective or completed"),
    ("pol:neg", "polarity", "negative"),
    ("mood:pot", "mood", "potential or ability"),
    ("clause:q", "clause", "question"),
    ("dem:prox", "deixis", "proximal"),
    ("dem:dist", "deixis", "distal"),
)

PRONOUNS = {
    "i": "ref:utterer", "me": "ref:utterer", "myself": "ref:utterer",
    "you": "ref:interlocutor", "yourself": "ref:interlocutor",
    "he": "ref:context", "him": "ref:context", "she": "ref:context", "her": "ref:context",
    "it": "ref:context", "itself": "ref:context",
    "we": "ref:utterer-set", "us": "ref:utterer-set",
    "they": "ref:context-set", "them": "ref:context-set",
}

IRREGULAR = {
    "am": "be", "are": "be", "is": "be", "was": "be", "were": "be", "been": "be",
    "bought": "buy", "ate": "eat", "drank": "drink", "gave": "give", "given": "give",
    "went": "go", "gone": "go", "came": "come", "seen": "see", "saw": "see",
    "took": "take", "taken": "take", "spoke": "speak", "spoken": "speak",
}
PAST_FORMS = frozenset({"was", "were", "had", "bought", "ate", "drank", "gave", "went", "came", "saw", "took", "spoke"})


def _canonical(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _word_lemma(word: str) -> str:
    word = IRREGULAR.get(word, word)
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("ing") and len(word) > 5:
        stem = word[:-3]
        if len(stem) > 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if word.endswith("ed") and len(word) > 4:
        stem = word[:-2]
        return stem[:-1] if len(stem) > 2 and stem[-1] == stem[-2] else stem
    if word.endswith("es") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and len(word) > 3:
        return word[:-1]
    return word


def _class(category: str | None, semantic_field: str | None) -> str:
    if category == "Person/Thing":
        return "noun"
    if category == "Action/Process":
        return "verb"
    if category == "Property":
        return "property"
    if semantic_field == "Time":
        return "adverb"
    return "operator"


def _orthography(seed: int, cfg) -> dict[str, str]:
    mapping = {segment: segment for segment in (*cfg.consonants, *cfg.vowels)}
    mapping["kʼ"] = "q" if seed % 2 == 0 else "k'"
    return mapping


def _form_pools(cfg, seed: int, count: int) -> tuple[list[str], list[str]]:
    marker_forms = sorted(legal_syllables(cfg))
    random.Random(seed ^ 0x4752414D).shuffle(marker_forms)
    marker_forms = marker_forms[: len(MARKER_SPECS)]
    reserved = {form.replace(".", "") for form in marker_forms}
    lexical = []
    seen = set()
    for root in generate_roots(cfg, [2]):
        plain = root.form.replace(".", "")
        if root.prominence != 0 or plain in reserved or plain in seen:
            continue
        seen.add(plain)
        lexical.append(root.form)
    lexical.sort(key=lambda form: (hashlib.sha256(f"{seed}|{form}".encode()).digest(), form))
    if len(lexical) < count:
        raise ValueError(f"phonological pool has {len(lexical)} forms for {count} concepts")
    return marker_forms, lexical[:count]


def build_working_language(
    *, inventory_path=DEFAULT_INVENTORY, phonology_path=DEFAULT_PHONOLOGY,
    possession_kinship_path=DEFAULT_POSSESSION_KINSHIP, seed=DEFAULT_SEED,
) -> dict:
    inventory = json.loads(Path(inventory_path).read_text(encoding="utf-8"))
    if inventory.get("schema") != "losica-semantic-inventory/1":
        raise ValueError("working language requires losica-semantic-inventory/1")
    concepts = sorted(inventory["concepts"], key=lambda row: int(row["concepticon_id"]))
    cfg = load_phonology(phonology_path)
    possession_kinship = load_possession_kinship(possession_kinship_path, inventory)
    spelling = _orthography(seed, cfg)
    marker_forms, lexical_forms = _form_pools(cfg, seed, len(concepts))
    markers = []
    for (semantic_id, marker_class, meaning), form in zip(MARKER_SPECS, marker_forms):
        markers.append({
            "semantic_id": semantic_id,
            "class": marker_class,
            "meaning": meaning,
            "form": form,
            "orthographic": orthographic_form(form, spelling, cfg),
            "provenance": "generated grammatical form; UniMorph/UD-shaped function",
        })
    lexicon = []
    for concept, form in zip(concepts, lexical_forms):
        concept_id = concept["concepticon_id"]
        lexicon.append({
            "semantic_id": f"c:{concept_id}",
            "links": [{"namespace": "concepticon", "object_id": concept_id}],
            "class": _class(concept.get("ontological_category"), concept.get("semantic_field")),
            "form": form,
            "orthographic": orthographic_form(form, spelling, cfg),
            "display": {"en": concept["gloss"].lower()},
            "definition": concept.get("definition"),
            "semantic_field": concept.get("semantic_field"),
            "ontological_category": concept.get("ontological_category"),
            "provenance": {
                "semantic_source": {"namespace": "concepticon", "object_id": concept_id},
                "form_assignment": "numeric semantic-ID order -> seed-shuffled legal-root pool",
                "seed": seed,
                "english_gloss_used_for_form_assignment": False,
            },
        })
    language = {
        "schema": SCHEMA,
        "version": "0.30.0",
        "seed": seed,
        "language_id": f"losica-working:{seed}:{inventory['source']['commit'][:12]}",
        "semantic_inventory": copy.deepcopy(inventory["source"]),
        "phonology": {
            "consonants": list(cfg.consonants), "vowels": list(cfg.vowels),
            "onsets": list(cfg.onsets), "codas": list(cfg.codas), "syllable": cfg.syllable,
            "rules": {"identical_consonant_degemination": True},
        },
        "orthography": {"segment_symbols": spelling},
        "grammar": {
            "clause_order": "SOV",
            "roles": ["AGENT", "PATIENT", "RECIPIENT", "BENEFICIARY", "TIME", "ATTRIBUTE"],
            "features": ["PST", "PROSP", "PFV", "NEG", "POT", "Q", "PROX", "DIST"],
            "temporal_interpretation": "unmarked predicates are tenseless; time words and discourse establish event time",
            "sources": ["Universal Dependencies 2.18", "UniMorph feature inventory"],
            "possession_kinship": {
                "schema": possession_kinship.schema,
                "nominal_order": list(possession_kinship.nominal_possession["order"]),
                "kin_order": list(possession_kinship.kin_relation["order"]),
                "compounds": {
                    compound_id: {
                        "meaning": compound.meaning,
                        "components": list(compound.components),
                        "head": compound.head,
                        "daughter_reflex_status": compound.daughter_reflex_status,
                    }
                    for compound_id, compound in possession_kinship.compounds.items()
                },
            },
        },
        "markers": markers,
        "lexicon": lexicon,
        "coverage": {
            "semantic_ids": len(lexicon),
            "generated_lexical_forms": len(lexicon),
            "generated_grammatical_forms": len(markers),
            "english_is_adapter_only": True,
        },
    }
    language["canonical_sha256"] = hashlib.sha256(
        json.dumps(language, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    validate_working_language(language)
    return language


def validate_working_language(language: dict) -> dict:
    if language.get("schema") != SCHEMA:
        raise ValueError("unsupported working-language schema")
    cfg_data = language["phonology"]
    from .config import PhonologyConfig
    cfg = PhonologyConfig(
        tuple(cfg_data["consonants"]), tuple(cfg_data["vowels"]),
        tuple(cfg_data["onsets"]), tuple(cfg_data["codas"]), cfg_data["syllable"],
    )
    rows = language["lexicon"] + language["markers"]
    forms = [row["orthographic"] for row in rows]
    ids = [row["semantic_id"] for row in rows]
    if len(forms) != len(set(forms)) or len(ids) != len(set(ids)):
        raise ValueError("working language requires unique forms and semantic IDs")
    if any(not is_legal_surface(row["form"], cfg) for row in rows):
        raise ValueError("working language contains an illegal form")
    canonical = copy.deepcopy(language)
    recorded_digest = canonical.pop("canonical_sha256", None)
    actual_digest = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if recorded_digest != actual_digest:
        raise ValueError("working language canonical digest mismatch")
    return {"status": "PASS", "lexemes": len(language["lexicon"]), "markers": len(language["markers"])}


def _indexes(language: dict):
    semantics = {row["semantic_id"]: row for row in language["lexicon"] + language["markers"]}
    surface = {row["orthographic"].casefold(): row for row in language["lexicon"] + language["markers"]}
    english: dict[str, list[dict]] = {}
    for row in language["lexicon"]:
        key = _canonical(row["display"]["en"])
        english.setdefault(key, []).append(row)
    return semantics, surface, english


def _english_tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"\bit['’]s\b", "it has" if re.search(r"\bit['’]s\s+.*\bbeen\b", text) else "it is", text)
    text = re.sub(r"\b(can|do|does|did|will|has|have|had|is|am|are|was|were)n['’]t\b", r"\1 not", text)
    return re.findall(r"[a-z0-9]+", text)


def _choose(rows: list[dict], preferred: tuple[str, ...]) -> dict:
    return next((row for kind in preferred for row in rows if row["class"] == kind), rows[0])


def _lookup_english(index: dict[str, list[dict]], word: str, preferred=("noun", "property", "adverb", "operator", "verb")) -> dict:
    lemma = _word_lemma(word)
    rows = index.get(lemma) or index.get(word)
    if not rows:
        raise KeyError(f"source-backed semantic lookup is empty for {word!r}")
    return _choose(rows, preferred)


def _ref(marker: str) -> dict:
    return {"type": "reference", "semantic_id": marker}


def _entity(row: dict, *, role: str, modifiers=None, deixis=None) -> dict:
    return {
        "type": "entity", "semantic_id": row["semantic_id"], "role": role,
        "modifiers": list(modifiers or []), **({"deixis": deixis} if deixis else {}),
    }


def parse_english(language: dict, text: str) -> dict:
    _, _, english = _indexes(language)
    words = _english_tokens(text)
    if not words:
        raise ValueError("translation requires source text")
    question = text.rstrip().endswith("?") or words[0] in {"can", "do", "does", "did", "is", "are", "was", "were", "has", "have"}
    features = []
    if "not" in words:
        features.append("pol:neg")
    if "will" in words:
        features.append("asp:pros")
    if any(word in PAST_FORMS or (word.endswith("ed") and len(word) > 4) for word in words):
        features.append("tam:pst")
    if any(word in {"has", "have", "had", "been"} for word in words):
        features.append("asp:pfv")
    if "can" in words:
        features.append("mood:pot")
    if question:
        features.append("clause:q")

    auxiliaries = {"can", "do", "does", "did", "will", "has", "have", "had", "not"}
    copulas = {"be", "am", "are", "is", "was", "were", "been"}
    determiners = {"a", "an", "the"}
    cursor = 0
    copula_seen = False
    while cursor < len(words) and words[cursor] in auxiliaries | copulas:
        copula_seen = copula_seen or words[cursor] in copulas
        cursor += 1
    if cursor >= len(words):
        raise ValueError("translation requires an explicit subject")
    subject_word = words[cursor]
    subject = _ref(PRONOUNS[subject_word]) if subject_word in PRONOUNS else _entity(
        _lookup_english(english, subject_word, ("noun",)), role="AGENT"
    )
    cursor += 1

    adjuncts = []
    while cursor < len(words) and words[cursor] in auxiliaries | copulas:
        copula_seen = copula_seen or words[cursor] in copulas
        cursor += 1
    while cursor < len(words):
        try:
            candidate = _lookup_english(english, words[cursor], ("adverb",))
        except KeyError:
            break
        if candidate["class"] != "adverb":
            break
        adjuncts.append({"type": "modifier", "semantic_id": candidate["semantic_id"], "role": "TIME" if candidate.get("semantic_field") == "Time" else "MANNER"})
        cursor += 1

    while cursor < len(words) and words[cursor] in auxiliaries | copulas:
        copula_seen = copula_seen or words[cursor] in copulas
        cursor += 1

    like_comparison = cursor < len(words) and words[cursor] == "like"
    if like_comparison:
        cursor += 1
    if copula_seen or like_comparison:
        while cursor < len(words) and words[cursor] in determiners:
            cursor += 1
        deixis = "PROX" if "this" in words[cursor:] else "DIST" if "that" in words[cursor:] else None
        if like_comparison:
            attribute = _lookup_english(english, "same", ("property", "operator"))
        else:
            attribute_word = next((word for word in words[cursor:] if word not in {"this", "that"}), "same")
            attribute = _lookup_english(english, attribute_word, ("property", "noun", "operator"))
        graph = {
            "type": "clause", "predicate": _lookup_english(english, "be", ("verb",))["semantic_id"],
            "arguments": {"THEME": subject, "ATTRIBUTE": _entity(attribute, role="ATTRIBUTE", deixis=deixis)},
            "adjuncts": adjuncts, "features": features,
        }
        return graph

    predicate = _lookup_english(english, words[cursor], ("verb",))
    cursor += 1
    arguments = {"AGENT": subject}
    pending_role = "PATIENT"
    noun_modifiers = []
    while cursor < len(words):
        word = words[cursor]
        cursor += 1
        if word in determiners or word in auxiliaries:
            continue
        if word in {"to", "for"}:
            pending_role = "RECIPIENT" if word == "to" else "BENEFICIARY"
            continue
        if word in PRONOUNS:
            arguments[pending_role] = _ref(PRONOUNS[word]) | {"role": pending_role}
            pending_role = "PATIENT"
            continue
        row = _lookup_english(english, word)
        if row["class"] in {"adverb", "operator"} and row.get("semantic_field") == "Time":
            adjuncts.append({"type": "modifier", "semantic_id": row["semantic_id"], "role": "TIME"})
        elif row["class"] == "property":
            noun_modifiers.append(row["semantic_id"])
        elif row["class"] == "noun":
            arguments[pending_role] = _entity(row, role=pending_role, modifiers=noun_modifiers)
            noun_modifiers = []
            pending_role = "PATIENT"
    return {"type": "clause", "predicate": predicate["semantic_id"], "arguments": arguments, "adjuncts": adjuncts, "features": features}


def _emit(language: dict, graph: dict) -> list[dict]:
    semantics, _, _ = _indexes(language)
    out = []

    def add(semantic_id: str, role=None):
        row = semantics[semantic_id]
        out.append({"semantic_id": semantic_id, "orthographic": row["orthographic"], "form": row["form"], "role": role, "gloss": row.get("display", {}).get("en") or row.get("meaning")})

    def add_argument(value: dict, role: str):
        add(value["semantic_id"], role)
        for modifier in value.get("modifiers", []):
            add(modifier, "MODIFIER")
        if value.get("deixis") == "PROX":
            add("dem:prox", "DEIXIS")
        elif value.get("deixis") == "DIST":
            add("dem:dist", "DEIXIS")
        if role == "PATIENT":
            add("role:acc", role)
        elif role in {"RECIPIENT", "BENEFICIARY"}:
            add("role:dat", role)

    if graph.get("type") in {"nominal_possession", "kin_relation", "clan_kin"}:
        inventory = {"concepts": [
            {"concepticon_id": row["semantic_id"].removeprefix("c:")}
            for row in language["lexicon"]
        ]}
        grammar = load_possession_kinship(DEFAULT_POSSESSION_KINSHIP, inventory)
        for semantic_id, role in nominal_sequence(graph, grammar):
            add(semantic_id, role)
        return out

    arguments = graph["arguments"]
    for role in ("AGENT", "THEME", "PATIENT", "RECIPIENT", "BENEFICIARY", "ATTRIBUTE"):
        if role in arguments:
            add_argument(arguments[role], role)
    for adjunct in graph.get("adjuncts", []):
        add(adjunct["semantic_id"], adjunct.get("role"))
    add(graph["predicate"], "PREDICATE")
    for feature in graph.get("features", []):
        add(feature, "FEATURE")
    return out


def translate(language: dict, source: str | dict) -> dict:
    graph = parse_english(language, source) if isinstance(source, str) else copy.deepcopy(source)
    tokens = _emit(language, graph)
    return {
        "source": source,
        "semantic_graph": graph,
        "losica": " ".join(token["orthographic"] for token in tokens),
        "phonemic": " ".join(token["form"] for token in tokens),
        "tokens": tokens,
        "state_mutated": False,
    }


def analyze(language: dict, text: str) -> dict:
    _, surface, _ = _indexes(language)
    tokens = []
    for value in text.casefold().split():
        if value not in surface:
            raise KeyError(f"unknown Losica form {value!r}")
        row = surface[value]
        tokens.append({
            "orthographic": value, "semantic_id": row["semantic_id"], "class": row["class"],
            "display_en": row.get("display", {}).get("en") or row.get("meaning"),
        })
    return {"losica": text, "tokens": tokens, "semantic_sequence": [row["semantic_id"] for row in tokens]}


def lookup(language: dict, query: str) -> list[dict]:
    semantics, surface, english = _indexes(language)
    key = _canonical(query)
    rows = []
    if query in semantics:
        rows.append(semantics[query])
    if query.casefold() in surface:
        rows.append(surface[query.casefold()])
    rows.extend(english.get(key, []))
    unique = {row["semantic_id"]: row for row in rows}
    return list(unique.values())


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Build or use the source-backed Losica working language")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    build.add_argument("--seed", type=int, default=DEFAULT_SEED)
    build.add_argument("--out", default="working-language.json")
    for name in ("translate", "analyze", "lookup"):
        command = sub.add_parser(name)
        command.add_argument("language")
        command.add_argument("text")
    args = parser.parse_args(argv)
    if args.command == "build":
        language = build_working_language(inventory_path=args.inventory, seed=args.seed)
        Path(args.out).write_text(json.dumps(language, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = {"out": args.out, **validate_working_language(language)}
    else:
        language = json.loads(Path(args.language).read_text(encoding="utf-8"))
        validate_working_language(language)
        result = {"translate": translate, "analyze": analyze, "lookup": lookup}[args.command](language, args.text)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
