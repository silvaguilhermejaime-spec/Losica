import random
from losica_engine.full_language import generate_complete_language
from losica_engine.grammar_v021 import LanguageExecutor, entity, semantic_equivalent
from losica_engine.numeral_system import compose_cardinal, decompose_cardinal, sample_numeral_system
from losica_engine.surface_analysis import analyze_surface


def _executor(state):
    return LanguageExecutor(lexicon=state["lexicon"], paradigms=state["paradigms"], morphology=state["morphology"], profile=state["profile"])


def _noun_probe(state):
    row = next(x for x in state["lexicon"] if x["class"] == "noun" and x.get("concept_mappings"))
    return row["concept"]


def test_generated_numeral_arithmetic_is_invertible_across_architectures():
    for seed in range(50):
        system, _ = sample_numeral_system(random.Random(seed), seed)
        limit = min(system["range"]["maximum"], 5000)
        samples = sorted({1, 2, 3, system["base"], system["base"] + 1, 2 * system["base"] + 3, min(123, limit), limit})
        for value in samples:
            atoms = decompose_cardinal(value, system)
            assert compose_cardinal(atoms, system) == value


def test_multi_atom_numerals_survive_written_surface_analysis():
    state = generate_complete_language(seed=19020, vocabulary_scale="core")
    executor = _executor(state); noun = _noun_probe(state)
    for value in (3, 10, 11, 21, 42, 99, 123, 999):
        graph = {"type": "phrase", "head": entity(noun, numeral=value), "construction": "numeral"}
        realization = executor.realize(graph)
        parsed = analyze_surface(state, realization["orthographic_sentence"])
        assert any(semantic_equivalent(graph, candidate) for candidate in parsed["analyses"])


def test_entity_semantics_use_generated_region_ids_with_probe_anchors():
    state = generate_complete_language(seed=19020, vocabulary_scale="core")
    plain = entity(_noun_probe(state))
    assert set(plain) == {"type", "number", "modifiers", "possessor", "deixis", "numeral", "quantifier", "concept"}
    assert plain["concept"].startswith("sr:")
    lexeme = next(row for row in state["lexicon"] if row["concept"] == plain["concept"])
    assert all(mapping["probe_id"].startswith("c:") for mapping in lexeme["concept_mappings"])


def test_final_scale_contains_512_seeded_probes_and_capabilities():
    state = generate_complete_language(seed=19020, vocabulary_scale="large", display_locale="en")
    mapped = {m["concept"] for x in state["lexicon"] for m in x.get("concept_mappings", [])}
    assert len(mapped) == 512
    assert state["metadata"]["concept_target"] == 512
    probes = {x["probe_id"]: x for x in state["capability_probes"]}
    assert probes["CAP-NESTED-EVENT-001"]["semantic_coverage"] is True
    assert probes["CAP-CARDINAL-123-001"]["semantic_coverage"] is True
