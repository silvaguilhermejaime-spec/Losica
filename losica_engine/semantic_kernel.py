"""Build Losica's minimal semantic kernel and its source-backed expansion.

The kernel follows the 65-meaning Natural Semantic Metalanguage (NSM)
inventory and adds four overt structural forms for deterministic written
parsing.  NSM is recorded as a research proposal, not as a proved universal.

Concepticon concepts form an optional expanded lexical layer.  The pinned
Concepticon release does not contain NSM explications, so this module never
invents them: expanded entries are explicitly marked as lexicalized source
concepts whose prime decomposition is not asserted.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from .config import PhonologyConfig, load_phonology
from .morphophonology import orthographic_form
from .phonology import generate_roots, is_legal_surface, legal_syllables
from .working_language import DEFAULT_INVENTORY, DEFAULT_PHONOLOGY, DEFAULT_SEED


SCHEMA = "losica-semantic-kernel/1"

PRIME_SOURCE = {
    "name": "Natural Semantic Metalanguage semantic primes",
    "version": "condensed chart 2022",
    "inventory_url": "https://nsm-approach.net/wp-content/uploads/2022/05/Chart-of-Primes_Condensed_2022.pdf",
    "review_doi": "10.22363/2687-0088-2021-25-2-317-342",
    "status": "research proposal; not a proved universal minimum",
}

# Stable numeric IDs make generated form assignment independent of the English
# exponents, which are source/display data only.  The ordering and group names
# follow the condensed 2022 NSM chart.
PRIME_SPECS = (
    ("nsm:001", "substantives", "I"),
    ("nsm:002", "substantives", "YOU"),
    ("nsm:003", "substantives", "SOMEONE"),
    ("nsm:004", "substantives", "SOMETHING~THING"),
    ("nsm:005", "substantives", "PEOPLE"),
    ("nsm:006", "substantives", "BODY"),
    ("nsm:007", "relational substantives", "KIND"),
    ("nsm:008", "relational substantives", "PART"),
    ("nsm:009", "determiners", "THIS"),
    ("nsm:010", "determiners", "THE SAME"),
    ("nsm:011", "determiners", "OTHER~ELSE"),
    ("nsm:012", "quantifiers", "ONE"),
    ("nsm:013", "quantifiers", "TWO"),
    ("nsm:014", "quantifiers", "SOME"),
    ("nsm:015", "quantifiers", "ALL"),
    ("nsm:016", "quantifiers", "MUCH~MANY"),
    ("nsm:017", "quantifiers", "LITTLE~FEW"),
    ("nsm:018", "evaluators", "GOOD"),
    ("nsm:019", "evaluators", "BAD"),
    ("nsm:020", "descriptors", "BIG"),
    ("nsm:021", "descriptors", "SMALL"),
    ("nsm:022", "mental predicates", "THINK"),
    ("nsm:023", "mental predicates", "KNOW"),
    ("nsm:024", "mental predicates", "WANT"),
    ("nsm:025", "mental predicates", "DON'T WANT"),
    ("nsm:026", "mental predicates", "FEEL"),
    ("nsm:027", "mental predicates", "SEE"),
    ("nsm:028", "mental predicates", "HEAR"),
    ("nsm:029", "speech", "SAY"),
    ("nsm:030", "speech", "WORDS"),
    ("nsm:031", "speech", "TRUE"),
    ("nsm:032", "actions events movement contact", "DO"),
    ("nsm:033", "actions events movement contact", "HAPPEN"),
    ("nsm:034", "actions events movement contact", "MOVE"),
    ("nsm:035", "actions events movement contact", "TOUCH"),
    ("nsm:036", "location existence possession specification", "BE (SOMEWHERE)"),
    ("nsm:037", "location existence possession specification", "THERE IS"),
    ("nsm:038", "location existence possession specification", "BE (SOMEONE/SOMETHING)"),
    ("nsm:039", "location existence possession specification", "(IS) MINE"),
    ("nsm:040", "life and death", "LIVE"),
    ("nsm:041", "life and death", "DIE"),
    ("nsm:042", "time", "WHEN~TIME"),
    ("nsm:043", "time", "NOW"),
    ("nsm:044", "time", "BEFORE"),
    ("nsm:045", "time", "AFTER"),
    ("nsm:046", "time", "A LONG TIME"),
    ("nsm:047", "time", "A SHORT TIME"),
    ("nsm:048", "time", "FOR SOME TIME"),
    ("nsm:049", "time", "MOMENT"),
    ("nsm:050", "space", "WHERE~PLACE"),
    ("nsm:051", "space", "HERE"),
    ("nsm:052", "space", "ABOVE"),
    ("nsm:053", "space", "BELOW"),
    ("nsm:054", "space", "FAR"),
    ("nsm:055", "space", "NEAR"),
    ("nsm:056", "space", "SIDE"),
    ("nsm:057", "space", "INSIDE"),
    ("nsm:058", "logical concepts", "NOT"),
    ("nsm:059", "logical concepts", "MAYBE"),
    ("nsm:060", "logical concepts", "CAN"),
    ("nsm:061", "logical concepts", "BECAUSE"),
    ("nsm:062", "logical concepts", "IF"),
    ("nsm:063", "intensifier augmentor", "VERY"),
    ("nsm:064", "intensifier augmentor", "MORE"),
    ("nsm:065", "similarity", "LIKE~AS~WAY"),
)

STRUCTURAL_SPECS = (
    ("struct:patient", "relator", "patient"),
    ("struct:recipient", "relator", "recipient or beneficiary"),
    ("struct:location", "relator", "spatial or temporal ground"),
    ("struct:question", "clause_operator", "question"),
)


def _orthography(seed: int, cfg: PhonologyConfig) -> dict[str, str]:
    mapping = {segment: segment for segment in (*cfg.consonants, *cfg.vowels)}
    mapping["kʼ"] = "q" if seed % 2 == 0 else "k'"
    return mapping


def _ranked(values, *, seed: int, namespace: str) -> list[str]:
    return sorted(
        values,
        key=lambda value: (
            hashlib.sha256(f"{seed}|{namespace}|{value}".encode()).digest(),
            value,
        ),
    )


def _kernel_rows(cfg: PhonologyConfig, spelling: dict[str, str], seed: int):
    specs = (*PRIME_SPECS, *STRUCTURAL_SPECS)
    forms = _ranked(legal_syllables(cfg), seed=seed, namespace="kernel")
    if len(forms) < len(specs):
        raise ValueError(f"phonological pool has {len(forms)} forms for {len(specs)} kernel meanings")
    assigned = {
        semantic_id: form
        for semantic_id, form in zip(sorted(spec[0] for spec in specs), forms)
    }
    primes = []
    for semantic_id, domain, exponent in PRIME_SPECS:
        form = assigned[semantic_id]
        primes.append({
            "semantic_id": semantic_id,
            "class": "root",
            "semantic_domain": domain,
            "source_exponent": {"en": exponent},
            "form": form,
            "orthographic": orthographic_form(form, spelling, cfg),
            "provenance": {
                "semantic_source": copy.deepcopy(PRIME_SOURCE),
                "form_assignment": "stable numeric semantic ID -> seed-ranked legal one-syllable pool",
                "seed": seed,
                "english_exponent_used_for_form_assignment": False,
            },
        })
    structural = []
    for semantic_id, word_class, meaning in STRUCTURAL_SPECS:
        form = assigned[semantic_id]
        structural.append({
            "semantic_id": semantic_id,
            "class": word_class,
            "meaning": meaning,
            "form": form,
            "orthographic": orthographic_form(form, spelling, cfg),
            "provenance": "Losica structural design for deterministic written parsing",
        })
    return primes, structural


def _expanded_lexicon(inventory: dict, cfg: PhonologyConfig, spelling: dict[str, str], seed: int):
    concepts = sorted(inventory["concepts"], key=lambda row: int(row["concepticon_id"]))
    candidates = []
    seen = set()
    for root in generate_roots(cfg, [2]):
        plain = root.form.replace(".", "")
        if root.prominence != 0 or plain in seen:
            continue
        seen.add(plain)
        candidates.append(root.form)
    forms = _ranked(candidates, seed=seed, namespace="expanded")
    if len(forms) < len(concepts):
        raise ValueError(f"phonological pool has {len(forms)} forms for {len(concepts)} expanded concepts")
    rows = []
    for concept, form in zip(concepts, forms):
        concept_id = concept["concepticon_id"]
        rows.append({
            "semantic_id": f"c:{concept_id}",
            "links": [{"namespace": "concepticon", "object_id": concept_id}],
            "class": "root",
            "representation": "lexicalized_source_concept",
            "prime_decomposition": "not_asserted",
            "form": form,
            "orthographic": orthographic_form(form, spelling, cfg),
            "display": {"en": concept["gloss"].lower()},
            "definition": concept.get("definition"),
            "semantic_field": concept.get("semantic_field"),
            "ontological_category": concept.get("ontological_category"),
            "provenance": {
                "semantic_source": {"namespace": "concepticon", "object_id": concept_id},
                "form_assignment": "numeric semantic ID -> seed-ranked legal two-syllable pool",
                "seed": seed,
                "english_gloss_used_for_form_assignment": False,
            },
        })
    return rows


def build_semantic_language(
    *,
    expanded: bool = True,
    inventory_path=DEFAULT_INVENTORY,
    phonology_path=DEFAULT_PHONOLOGY,
    seed: int = DEFAULT_SEED,
) -> dict:
    """Build the 69-form kernel and, by default, its Concepticon expansion."""
    inventory = json.loads(Path(inventory_path).read_text(encoding="utf-8"))
    if inventory.get("schema") != "losica-semantic-inventory/1":
        raise ValueError("semantic language requires losica-semantic-inventory/1")
    cfg = load_phonology(phonology_path)
    spelling = _orthography(seed, cfg)
    primes, structural = _kernel_rows(cfg, spelling, seed)
    lexicon = _expanded_lexicon(inventory, cfg, spelling, seed) if expanded else []
    language = {
        "schema": SCHEMA,
        "version": "0.30.0",
        "seed": seed,
        "language_id": f"losica-semantic:{seed}:{inventory['source']['commit'][:12]}",
        "semantic_inventory": copy.deepcopy(inventory["source"]),
        "semantic_kernel": {
            "prime_source": copy.deepcopy(PRIME_SOURCE),
            "primes": primes,
            "structural_forms": structural,
            "size": 69,
        },
        "grammatical_system": {
            "classes": {
                "root": {"openness": "open", "function": "category-neutral semantic material"},
                "relator": {"openness": "closed", "function": "overt argument or ground relation"},
                "clause_operator": {"openness": "closed", "function": "clause force or structure"},
            },
            "root_construction_roles": [
                "reference", "predicate", "entity_modifier", "event_modifier",
                "quantifier", "clause_connector",
            ],
            "clause_order": "SOV",
            "unmarked_role": "AGENT",
        },
        "phonology": {
            "consonants": list(cfg.consonants),
            "vowels": list(cfg.vowels),
            "onsets": list(cfg.onsets),
            "codas": list(cfg.codas),
            "syllable": cfg.syllable,
            "rules": {"identical_consonant_degemination": True},
        },
        "orthography": {"segment_symbols": spelling},
        "lexicon": lexicon,
        "expansion_policy": {
            "source": "pinned Concepticon inventory",
            "representation": "lexicalized source concepts",
            "prime_decomposition": "not asserted without a cited explication",
            "english_is_adapter_only": True,
        },
        "coverage": {
            "semantic_primes": len(primes),
            "structural_forms": len(structural),
            "kernel_forms": len(primes) + len(structural),
            "expanded_lexemes": len(lexicon),
            "grammatical_classes": 3,
        },
    }
    language["canonical_sha256"] = hashlib.sha256(
        json.dumps(language, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    validate_semantic_language(language)
    return language


def validate_semantic_language(language: dict) -> dict:
    if language.get("schema") != SCHEMA:
        raise ValueError("unsupported semantic-kernel schema")
    kernel = language["semantic_kernel"]
    primes = kernel["primes"]
    structural = kernel["structural_forms"]
    lexicon = language["lexicon"]
    if len(primes) != 65 or len(structural) != 4 or kernel.get("size") != 69:
        raise ValueError("semantic kernel requires exactly 65 primes and four structural forms")
    classes = language["grammatical_system"]["classes"]
    if set(classes) != {"root", "relator", "clause_operator"}:
        raise ValueError("semantic language requires exactly three grammatical classes")
    if any(row["class"] != "root" for row in (*primes, *lexicon)):
        raise ValueError("all semantic material must use the category-neutral root class")
    if any(row.get("prime_decomposition") != "not_asserted" for row in lexicon):
        raise ValueError("expanded concepts cannot claim an uncited prime decomposition")
    rows = [*primes, *structural, *lexicon]
    ids = [row["semantic_id"] for row in rows]
    forms = [row["orthographic"] for row in rows]
    if len(ids) != len(set(ids)) or len(forms) != len(set(forms)):
        raise ValueError("semantic language requires unique semantic IDs and forms")
    cfg_data = language["phonology"]
    cfg = PhonologyConfig(
        tuple(cfg_data["consonants"]),
        tuple(cfg_data["vowels"]),
        tuple(cfg_data["onsets"]),
        tuple(cfg_data["codas"]),
        cfg_data["syllable"],
    )
    if any(not is_legal_surface(row["form"], cfg) for row in rows):
        raise ValueError("semantic language contains an illegal form")
    canonical = copy.deepcopy(language)
    recorded_digest = canonical.pop("canonical_sha256", None)
    actual_digest = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if recorded_digest != actual_digest:
        raise ValueError("semantic language canonical digest mismatch")
    return {
        "status": "PASS",
        "kernel_forms": len(primes) + len(structural),
        "expanded_lexemes": len(lexicon),
        "grammatical_classes": len(classes),
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Build Losica's minimal semantic kernel and expansion")
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--kernel-only", action="store_true")
    parser.add_argument("--out", default="semantic-language.json")
    args = parser.parse_args(argv)
    language = build_semantic_language(
        expanded=not args.kernel_only,
        inventory_path=args.inventory,
        seed=args.seed,
    )
    Path(args.out).write_text(
        json.dumps(language, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out": args.out, **validate_semantic_language(language)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
