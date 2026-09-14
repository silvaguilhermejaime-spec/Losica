"""Optional post-generation history, usage, and population contracts."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def productivity_profile(events: list[dict], process_id: str, *, novel_host_trials: list[dict] | None = None) -> dict:
    relevant = [e for e in events if e.get("process_id") == process_id]
    token_frequency = sum(int(e.get("count", 1)) for e in relevant)
    hosts = Counter()
    for event in relevant:
        hosts[event.get("host_lexeme_id")] += int(event.get("count", 1))
    type_frequency = len(hosts)
    hapax_count = sum(v == 1 for v in hosts.values())
    by_generation = Counter(int(e.get("generation", 0)) for e in relevant)
    generations = sorted(by_generation)
    expanding = None
    if len(generations) >= 2:
        expanding = (by_generation[generations[-1]] - by_generation[generations[0]]) / max(1, sum(by_generation.values()))
    trials = novel_host_trials or []
    successes = sum(bool(x.get("accepted")) for x in trials)
    return {
        "process_id": process_id, "N_token_frequency": token_frequency, "V_type_frequency": type_frequency,
        "n1_hapax_count": hapax_count, "P_potential_productivity": hapax_count / token_frequency if token_frequency else None,
        "expanding_productivity": expanding, "novel_host_generalization": successes / len(trials) if trials else None,
        "measurement_provenance": ["Baayen 1992/1993/1994", "Baayen & Renouf 1996", "Plag, Dalton-Puffer & Baayen 1999"],
    }


def initial_history(language: dict) -> dict:
    return {
        "schema": "losica-history/2",
        "current_generation": 0,
        "canonical_sound_change_engine": "Lexurgy",
        "stages": [{
            "stage_id": "GEN-000-SYNCHRONIC", "generation": 0, "parent_stage_id": None,
            "lexicon_forms": {x["lexeme_id"]: x["form"] for x in language["lexicon"]},
            "operations": [], "provenance": {"source": "direct Losica generator", "seed": language["seed"]},
        }],
        "usage_state_variables": {
            "construction_token_frequency": {}, "construction_type_frequency": {}, "lexical_frequency": {},
            "chunking": {}, "phonological_reduction": {}, "distributional_expansion": {}, "constructional_reanalysis": {},
            "source": ["Bybee 2006", "Bybee 2011"],
        },
        "population_stages": [],
        "adapters": {
            "LanguageEvolution": {"direction": "bidirectional", "export_schema": "losica-languageevolution-experiment/1", "import_schema": "losica-population-history-stage/1"},
            "Lexurgy": {"direction": "bidirectional trace contract", "canonical_runtime": True, "rules_and_version_required": True},
            "Brassica": {"direction": "bidirectional trace contract", "canonical_runtime": False, "supports": ["stress", "tone", "iterative", "sporadic", "cross-word", "paradigm"]},
            "EGG": {"direction": "experimental export/import", "outputs_separate": True},
            "iterated_transmission": {"basis": "Kirby, Cornish & Smith 2008", "operates_after_generation": True},
        },
    }


def export_sound_change_stage(language: dict, directory: str | Path, *, engine: str, rules_text: str, engine_version: str) -> dict:
    if engine not in {"Lexurgy", "Brassica"}:
        raise ValueError("canonical sound-change engine must be Lexurgy or Brassica")
    root = Path(directory); root.mkdir(parents=True, exist_ok=True)
    forms = root / "forms.tsv"; rules = root / ("rules.lsc" if engine == "Lexurgy" else "rules.brassica")
    forms.write_text("lexeme_id\tform\n" + "".join(f"{x['lexeme_id']}\t{x['form']}\n" for x in language["lexicon"]), encoding="utf-8")
    rules.write_text(rules_text, encoding="utf-8")
    manifest = {"schema": "losica-sound-change-export/1", "engine": engine, "engine_version": engine_version, "rules_file": rules.name, "forms_file": forms.name, "input_stage_id": language["history"]["stages"][-1]["stage_id"]}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def import_sound_change_trace(path: str | Path, language: dict, *, engine: str, engine_version: str, rules_sha256: str) -> dict:
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        required = {"lexeme_id", "input", "output", "rule_trace"}
        if not required <= set(header):
            raise ValueError(f"sound-change trace requires columns {sorted(required)}")
        for line in handle:
            values = line.rstrip("\n").split("\t")
            rows.append(dict(zip(header, values)))
    known = {x["lexeme_id"] for x in language["lexicon"]}
    if any(r["lexeme_id"] not in known for r in rows):
        raise ValueError("sound-change trace references an unknown lexeme")
    generation = language["history"]["current_generation"] + 1
    stage = {
        "stage_id": f"GEN-{generation:03d}-{engine.upper()}", "generation": generation,
        "parent_stage_id": language["history"]["stages"][-1]["stage_id"],
        "lexicon_forms": {r["lexeme_id"]: r["output"] for r in rows}, "operations": rows,
        "provenance": {"engine": engine, "engine_version": engine_version, "rules_sha256": rules_sha256, "trace_file": str(path)},
    }
    language["history"]["stages"].append(stage); language["history"]["current_generation"] = generation
    return stage


def run_usage_stage(language: dict, *, generations: int) -> dict:
    """Interleave measurable usage, morphology, sound, analogy, and transmission."""
    if generations < 1:
        return language["history"]
    state = language["history"]["usage_state_variables"]
    for offset in range(1, generations + 1):
        generation = language["history"]["current_generation"] + 1
        operations = []
        for example in language["examples"]:
            cid = example["construction_id"]
            state["construction_token_frequency"][cid] = state["construction_token_frequency"].get(cid, 0) + 1
            state["construction_type_frequency"].setdefault(cid, len({x.get("concept") for x in example["token_details"]}))
            if state["construction_token_frequency"][cid] >= 2:
                state["chunking"][cid] = {"status": "conventionalized_sequence", "generation": generation}
            if state["construction_token_frequency"][cid] >= 3:
                state["distributional_expansion"][cid] = {"licensed_contexts": ["main", "embedded"], "generation": generation}
            for token in example["token_details"]:
                lid = token["lexeme_id"]; state["lexical_frequency"][lid] = state["lexical_frequency"].get(lid, 0) + 1
                if state["lexical_frequency"][lid] >= 4:
                    state["phonological_reduction"][lid] = {"eligible": True, "generation": generation, "conditioning": "high token frequency"}
        operations.append({"operation": "usage_update", "construction_tokens": len(language["examples"]), "tracked_variables": ["construction_token_frequency", "construction_type_frequency", "lexical_frequency", "chunking", "phonological_reduction", "distributional_expansion"]})

        process_ids = sorted(language["morphology"]["derivation"])
        process = process_ids[(language["seed"] + generation) % len(process_ids)] if process_ids else None
        operations.append({"operation": "morphological_change", "process_id": process, "change": "productivity_observation", "generation": generation})

        prior_forms = dict(language["history"]["stages"][-1]["lexicon_forms"])
        changed_forms = dict(prior_forms)
        ordered_ids = sorted(prior_forms)
        changed_id = ordered_ids[(language["seed"] + generation) % len(ordered_ids)] if ordered_ids else None
        if changed_id:
            old = prior_forms[changed_id]
            vowel_cycle = {"a": "i", "i": "u", "u": "a"}
            position = next((i for i, char in enumerate(old) if char in vowel_cycle), None)
            new = old if position is None else old[:position] + vowel_cycle[old[position]] + old[position + 1:]
            changed_forms[changed_id] = new
            operations.append({"operation": "sound_change", "engine": "Losica native history scheduler", "lexeme_id": changed_id, "input": old, "output": new, "rule": "first-vowel chain shift", "active_stage_validity": "vowel substitution preserves (C)V(C) syllabification"})

        analogy_target = ordered_ids[(language["seed"] + generation + 1) % len(ordered_ids)] if ordered_ids else None
        operations.append({"operation": "analogy", "lexeme_id": analogy_target, "change": "paradigm pattern reinforcement", "form_changed": False})
        operations.append({"operation": "transmission", "learner_generation": generation, "seed": language["seed"], "bottleneck_examples": len(language["examples"]), "population_adapter": "LanguageEvolution-compatible"})
        stage = {
            "stage_id": f"GEN-{generation:03d}-EVOLUTION", "generation": generation,
            "parent_stage_id": language["history"]["stages"][-1]["stage_id"],
            "lexicon_forms": changed_forms,
            "operations": operations,
            "provenance": {"source": ["Bybee 2006", "Bybee 2011"], "seed": language["seed"], "generation": generation},
        }
        language["history"]["stages"].append(stage); language["history"]["current_generation"] = generation
    return language["history"]
