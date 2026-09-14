"""Canonical JSON, TSV, CLDF, grammar, examples, and provenance export."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from .config import load_phonology
from .phonology import tokenize_surface


def _has_english_display(state: dict) -> bool:
    return any("en" in row.get("display", {}) for row in state.get("lexicon", []))


def _parameter_name(lexeme: dict, mapping: dict, english: bool) -> str:
    if english:
        aliases = lexeme.get("display", {}).get("en_aliases", [])
        mappings = lexeme.get("concept_mappings", [])
        if aliases and mapping in mappings:
            index = mappings.index(mapping)
            if index < len(aliases):
                return aliases[index]
        label = lexeme.get("display", {}).get("en")
        if label:
            return label
    return mapping.get("concept") or lexeme.get("concept") or lexeme["lexeme_id"]


def _parameter_description(mapping: dict, english: bool) -> str:
    if english and mapping.get("definition"):
        return mapping["definition"]
    return mapping.get("concept") or "generated grammatical semantic ID"


def _write_tsv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def _fallback_table(url: str, conforms: str | None, columns: list[tuple[str, str | None, bool]], primary="ID", foreign_keys=None) -> dict:
    table = {
        "url": url,
        "tableSchema": {
            "columns": [{**{"name": name, "datatype": "string", "required": required}, **({"propertyUrl": prop} if prop else {})} for name, prop, required in columns],
            "primaryKey": primary,
        },
    }
    if conforms: table["dc:conformsTo"] = f"http://cldf.clld.org/v1.0/terms.rdf#{conforms}"
    if foreign_keys: table["tableSchema"]["foreignKeys"] = foreign_keys
    return table


def _export_cldf_fallback(state: dict, root: Path) -> Path:
    """Write standards-shaped CLDF through the built-in fallback.

    Release validation exercises the same output through pycldf; this path
    keeps the primary command usable before optional validation dependencies
    are installed.
    """
    root.mkdir(parents=True, exist_ok=True)
    cfg = load_phonology(Path(__file__).resolve().parents[1] / "config/preproto.json")
    english = _has_english_display(state)
    forms, params = [], {}
    for lexeme in state["lexicon"]:
        mappings = lexeme.get("concept_mappings") or [{"concepticon_id": None, "concept": lexeme.get("concept", lexeme["lexeme_id"])}]
        for j, mapping in enumerate(mappings, 1):
            pid = mapping.get("concepticon_id") or f"GRAM-{lexeme['lexeme_id']}"
            params.setdefault(pid, {"ID": pid, "Name": _parameter_name(lexeme, mapping, english), "Description": _parameter_description(mapping, english), "ColumnSpec": ""})
            forms.append({"ID": f"{lexeme['lexeme_id']}-{j}", "Language_ID": "losica", "Parameter_ID": pid, "Form": lexeme.get("orthographic", lexeme["form"].replace(".", "")), "Segments": " ".join(tokenize_surface(lexeme["form"].replace(".", ""), cfg.consonants, cfg.vowels)), "Comment": lexeme["form"], "Source": "Concepticon340" if mapping.get("concepticon_id") else ""})
    _write_csv = lambda name, fields, data: _write_delimited(root / name, fields, data, ",")
    _write_csv("forms.csv", ["ID", "Language_ID", "Parameter_ID", "Form", "Segments", "Comment", "Source"], forms)
    languages = [{"ID": "losica", "Name": state["metadata"]["name"], "Macroarea": "Losica world"}]
    if english:
        languages.append({"ID": "eng", "Name": "English", "Macroarea": "Eurasia", "ISO639P3code": "eng"})
    _write_csv("languages.csv", ["ID", "Name", "Macroarea", "Latitude", "Longitude", "Glottocode", "ISO639P3code"], languages)
    _write_csv("parameters.csv", ["ID", "Name", "Description", "ColumnSpec"], list(params.values()))
    exrows = [{"ID": f"EX-{i:03d}", "Language_ID": "losica", "Primary_Text": x["orthographic_sentence"], "Analyzed_Word": "\t".join(x["orthographic_tokens"]), "Gloss": "\t".join(t["gloss"] for t in x["token_details"]), "Translated_Text": x["translation"] if english else "", "Meta_Language_ID": "eng" if english else "", "LGR_Conformance": "", "Comment": x["construction_id"]} for i, x in enumerate(state["examples"], 1)]
    _write_csv("examples.csv", ["ID", "Language_ID", "Primary_Text", "Analyzed_Word", "Gloss", "Translated_Text", "Meta_Language_ID", "LGR_Conformance", "Comment"], exrows)
    paradigm_rows = []
    for lid, cells in state["paradigms"].items():
        if lid in {"sample_noun", "sample_verb"}: continue
        for i, cell in enumerate(cells, 1):
            paradigm_rows.append({"ID": f"{lid}-P{i:04d}", "Lexeme_ID": lid, "Feature_Bundle": json.dumps(cell["feature_bundle"], sort_keys=True), "Phonemic": cell["form"], "Orthographic": cell["orthographic"], "Underlying": cell["underlying_form"], "Provenance": "UniMorph-shaped Losica paradigm executor"})
    feature_rows = [{"ID": x["feature_id"], "Source": x["source"], "Value": json.dumps(x["value"], ensure_ascii=False, sort_keys=True), "Executor": x["executor"], "Provenance": x.get("property_path", "sampled typological profile")} for x in state["profile"]["feature_executions"]]
    provenance_rows = [{"ID": f"PR-{i:05d}", "Entity": node.get("entity", "decision"), "Representation": node.get("representation", "record"), "Inputs": json.dumps(node.get("inputs", node.get("source_ids", [])), ensure_ascii=False, sort_keys=True), "Transformation": node.get("transformation", node.get("sampling_method", "record")), "Outputs": json.dumps(node.get("outputs", [node.get("value")]), ensure_ascii=False, sort_keys=True), "Source": node.get("source", "Losica")} for i, node in enumerate(state["provenance_graph"]["nodes"], 1)]
    history_rows = [{"ID": f"{stage['stage_id']}:{lid}", "Stage_ID": stage["stage_id"], "Parent_Stage_ID": stage.get("parent_stage_id") or "", "Generation": stage["generation"], "Lexeme_ID": lid, "Form": form, "Provenance": json.dumps(stage.get("provenance", {}), ensure_ascii=False, sort_keys=True)} for stage in state["history"]["stages"] for lid, form in stage["lexicon_forms"].items()]
    _write_csv("paradigms.csv", ["ID", "Lexeme_ID", "Feature_Bundle", "Phonemic", "Orthographic", "Underlying", "Provenance"], paradigm_rows)
    _write_csv("features.csv", ["ID", "Source", "Value", "Executor", "Provenance"], feature_rows)
    _write_csv("provenance.csv", ["ID", "Entity", "Representation", "Inputs", "Transformation", "Outputs", "Source"], provenance_rows)
    _write_csv("history.csv", ["ID", "Stage_ID", "Parent_Stage_ID", "Generation", "Lexeme_ID", "Form", "Provenance"], history_rows)
    (root / "sources.bib").write_text("@misc{Concepticon340, title={Concepticon 3.4.0}, doi={10.5281/zenodo.21373838}}\n@misc{CLICS4v1, title={CLICS4 v1.0}, doi={10.5281/zenodo.16900179}}\n@misc{Grambankv1, title={Grambank v1.0}}\n@misc{WALS20204, title={WALS Online v2020.4}}\n@misc{UniMorph, title={Universal Morphology}}\n@misc{UD2, title={Universal Dependencies v2}}\n", encoding="utf-8")
    fk_lang = {"columnReference": "Language_ID", "reference": {"resource": "languages.csv", "columnReference": "ID"}}
    fk_param = {"columnReference": "Parameter_ID", "reference": {"resource": "parameters.csv", "columnReference": "ID"}}
    term = "http://cldf.clld.org/v1.0/terms.rdf#"
    metadata = {
        "@context": ["http://www.w3.org/ns/csvw", {"@language": "und"}], "dc:conformsTo": term + "Wordlist", "dc:source": "sources.bib",
        "tables": [
            _fallback_table("forms.csv", "FormTable", [("ID", term+"id", True), ("Language_ID", term+"languageReference", True), ("Parameter_ID", term+"parameterReference", True), ("Form", term+"form", True), ("Segments", term+"segments", False), ("Comment", term+"comment", False), ("Source", term+"source", False)], foreign_keys=[fk_lang, fk_param]),
            _fallback_table("languages.csv", "LanguageTable", [("ID", term+"id", True), ("Name", term+"name", False), ("Macroarea", term+"macroarea", False), ("Latitude", term+"latitude", False), ("Longitude", term+"longitude", False), ("Glottocode", term+"glottocode", False), ("ISO639P3code", term+"iso639P3code", False)]),
            _fallback_table("parameters.csv", "ParameterTable", [("ID", term+"id", True), ("Name", term+"name", False), ("Description", term+"description", False), ("ColumnSpec", term+"columnSpec", False)]),
            _fallback_table("examples.csv", "ExampleTable", [("ID", term+"id", True), ("Language_ID", term+"languageReference", True), ("Primary_Text", term+"primaryText", True), ("Analyzed_Word", term+"analyzedWord", False), ("Gloss", term+"gloss", False), ("Translated_Text", term+"translatedText", False), ("Meta_Language_ID", term+"metaLanguageReference", False), ("LGR_Conformance", term+"lgrConformance", False), ("Comment", term+"comment", False)]),
            _fallback_table("paradigms.csv", None, [(x, None, x == "ID") for x in ["ID", "Lexeme_ID", "Feature_Bundle", "Phonemic", "Orthographic", "Underlying", "Provenance"]]),
            _fallback_table("features.csv", None, [(x, None, x == "ID") for x in ["ID", "Source", "Value", "Executor", "Provenance"]]),
            _fallback_table("provenance.csv", None, [(x, None, x == "ID") for x in ["ID", "Entity", "Representation", "Inputs", "Transformation", "Outputs", "Source"]]),
            _fallback_table("history.csv", None, [(x, None, x == "ID") for x in ["ID", "Stage_ID", "Parent_Stage_ID", "Generation", "Lexeme_ID", "Form", "Provenance"]]),
        ],
    }
    # CLDF sequence-valued columns carry explicit CSVW separators.
    for table in metadata["tables"]:
        for column in table["tableSchema"]["columns"]:
            if (table["url"], column["name"]) in {("forms.csv", "Segments"), ("forms.csv", "Source")}:
                column["separator"] = " " if column["name"] == "Segments" else ";"
            if (table["url"], column["name"]) in {("examples.csv", "Analyzed_Word"), ("examples.csv", "Gloss")}:
                column["separator"] = "\t"
    target = root / "Wordlist-metadata.json"; target.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _write_delimited(path: Path, fields: list[str], rows: list[dict], delimiter: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", delimiter=delimiter, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def export_cldf(state: dict, directory: str | Path) -> Path:
    root = Path(directory)
    try:
        from pycldf import Wordlist
        from pycldf.sources import Source
    except ImportError:
        return _export_cldf_fallback(state, root)
    root.mkdir(parents=True, exist_ok=True)
    for name in ("Wordlist-metadata.json", "forms.csv", "languages.csv", "parameters.csv", "examples.csv", "sources.bib", "paradigms.csv", "features.csv", "provenance.csv", "history.csv"):
        p = root / name
        if p.exists(): p.unlink()
    ds = Wordlist.in_dir(root)
    ds.add_component("LanguageTable"); ds.add_component("ParameterTable"); ds.add_component("ExampleTable")
    ds.add_table("paradigms.csv", "ID", "Lexeme_ID", "Feature_Bundle", "Phonemic", "Orthographic", "Underlying", "Provenance")
    ds.add_table("features.csv", "ID", "Source", "Value", "Executor", "Provenance")
    ds.add_table("provenance.csv", "ID", "Entity", "Representation", "Inputs", "Transformation", "Outputs", "Source")
    ds.add_table("history.csv", "ID", "Stage_ID", "Parent_Stage_ID", "Generation", "Lexeme_ID", "Form", "Provenance")
    ds.add_sources(
        Source("misc", "Concepticon340", title="Concepticon 3.4.0", doi="10.5281/zenodo.21373838"),
        Source("misc", "CLICS4v1", title="CLICS4 v1.0", doi="10.5281/zenodo.16900179"),
        Source("misc", "Grambankv1", title="Grambank v1.0"),
        Source("misc", "WALS20204", title="WALS Online v2020.4"),
        Source("misc", "UniMorph", title="Universal Morphology schema and datasets"),
        Source("misc", "UD2", title="Universal Dependencies v2"),
    )
    cfg = load_phonology(Path(__file__).resolve().parents[1] / "config/preproto.json")
    english = _has_english_display(state)
    forms, parameters = [], {}
    for lexeme in state["lexicon"]:
        mappings = lexeme.get("concept_mappings") or [{"concepticon_id": None, "concept": lexeme.get("concept", lexeme["lexeme_id"])}]
        for j, mapping in enumerate(mappings, 1):
            pid = mapping.get("concepticon_id") or f"GRAM-{lexeme['lexeme_id']}"
            parameters.setdefault(pid, {"ID": pid, "Name": _parameter_name(lexeme, mapping, english), "Description": _parameter_description(mapping, english)})
            forms.append({
                "ID": f"{lexeme['lexeme_id']}-{j}", "Language_ID": "losica", "Parameter_ID": pid,
                "Form": lexeme.get("orthographic", lexeme["form"].replace(".", "")),
                "Segments": list(tokenize_surface(lexeme["form"].replace(".", ""), cfg.consonants, cfg.vowels)),
                "Comment": json.dumps({"lexeme_id": lexeme["lexeme_id"], "phonemic": lexeme["form"], "formation": lexeme["formation"]}, ensure_ascii=False, sort_keys=True),
                "Source": ["Concepticon340"] if mapping.get("concepticon_id") else [],
            })
    examples = [{
        "ID": f"EX-{i:03d}", "Language_ID": "losica", "Primary_Text": x["orthographic_sentence"],
        "Analyzed_Word": x["orthographic_tokens"], "Gloss": [t["gloss"] for t in x["token_details"]],
        "Translated_Text": x["translation"] if english else "", "Meta_Language_ID": "eng" if english else "", "Comment": x["construction_id"],
    } for i, x in enumerate(state["examples"], 1)]
    paradigm_rows = []
    for lid, cells in state["paradigms"].items():
        if lid in {"sample_noun", "sample_verb"}: continue
        for i, cell in enumerate(cells, 1):
            paradigm_rows.append({"ID": f"{lid}-P{i:04d}", "Lexeme_ID": lid, "Feature_Bundle": json.dumps(cell["feature_bundle"], sort_keys=True), "Phonemic": cell["form"], "Orthographic": cell["orthographic"], "Underlying": cell["underlying_form"], "Provenance": "UniMorph-shaped Losica paradigm executor"})
    feature_rows = [{"ID": x["feature_id"], "Source": x["source"], "Value": json.dumps(x["value"], ensure_ascii=False, sort_keys=True), "Executor": x["executor"], "Provenance": x.get("property_path", "sampled typological profile")} for x in state["profile"]["feature_executions"]]
    provenance_rows = []
    for i, node in enumerate(state["provenance_graph"]["nodes"], 1):
        provenance_rows.append({"ID": f"PR-{i:05d}", "Entity": node.get("entity", node.get("type", "decision")), "Representation": node.get("representation", "record"), "Inputs": json.dumps(node.get("inputs", node.get("source_ids", [])), ensure_ascii=False, sort_keys=True), "Transformation": node.get("transformation", node.get("sampling_method", "record")), "Outputs": json.dumps(node.get("outputs", [node.get("value")]), ensure_ascii=False, sort_keys=True), "Source": node.get("source", "Losica")})
    history_rows = [{"ID": f"{stage['stage_id']}:{lid}", "Stage_ID": stage["stage_id"], "Parent_Stage_ID": stage.get("parent_stage_id") or "", "Generation": stage["generation"], "Lexeme_ID": lid, "Form": form, "Provenance": json.dumps(stage.get("provenance", {}), ensure_ascii=False, sort_keys=True)} for stage in state["history"]["stages"] for lid, form in stage["lexicon_forms"].items()]
    ds.write(
        FormTable=forms,
        LanguageTable=([
            {"ID": "losica", "Name": state["metadata"]["name"], "Macroarea": "Losica world", "Latitude": None, "Longitude": None},
        ] + ([{"ID": "eng", "Name": "English", "Macroarea": "Eurasia", "Latitude": None, "Longitude": None, "ISO639P3code": "eng"}] if english else [])),
        ParameterTable=list(parameters.values()), ExampleTable=examples,
        **{"paradigms.csv": paradigm_rows, "features.csv": feature_rows, "provenance.csv": provenance_rows, "history.csv": history_rows},
    )
    return root / "Wordlist-metadata.json"


def render_grammar(state: dict) -> str:
    p, m = state["profile"], state["morphology"]
    return f"""# {state['metadata']['name']} grammar

## Generation

An empirical joint profile enters the typed construction inventory. The profile selects `{p['syntax']['clause_order']}` clause order, `{p['syntax']['adposition_order']}` adpositions, `{p['syntax']['genitive_order']}` genitives, `{p['syntax']['property_order']}` property modifiers, and `{p['syntax']['numeral_order']}` numerals. Each choice calls the executor named in the provenance table and produces the corresponding order in every applicable construction.

## Phonology and prosody

A morpheme sequence is tokenized in the active Losica inventory, boundary rules repair unlicensed clusters, the `(C)V(C)` grammar syllabifies the result, and the `{p['prosody']['word_prominence_rule']}` rule selects exactly one prominent syllable. The orthography then maps the surface segment sequence to graphemes while retaining the phonemic form.

## Lexicon

Concepticon concepts enter lexical allocation. Weighted CLICS4 edges may join concepts in one lexeme, while an independent phonotactic root remains the alternative. Environmental events enter through a separate waveform → vocal-imitation ranking → phone hypothesis → Losica mapping path. The generated state contains {len(state['lexicon'])} lexemes and {sum(len(x.get('concept_mappings', [])) for x in state['lexicon'])} concept mappings.

## Morphology

Feature bundles enter the UniMorph-shaped paradigm executor. The nominal template is `{m['noun']['template']}` and the verbal template is `{m['verb']['template']}`. Concatenation passes through the same morphophonological and prosodic pipeline as lexical roots. Zero realization, generated subject-index exponence, multiple exponence, phonological allomorphy, syncretism, and explicit paradigm gaps are stored as grammar facts.

## Constructions and semantics

A typed predicate–argument graph selects a form–meaning construction. Semantic roles map to dependency relations and licensed cases; the sampled profile then orders arguments, predicates, modifiers, adpositions, complementizers, and particles. The same token annotations reconstruct the typed meaning during analysis. The inventory covers intransitive, transitive, ditransitive, copular, existential, possessive, locative, modification, numeral, quantification, negation, polar and content questions, imperatives, coordination, complementation, relative clauses, and adverbial subordination.

## Reference and numerals

The participant-reference system is `{p['reference_system']['system_id']}` with {len(p['reference_system']['cells'])} independently generated reference cells. Subject indexing uses `{p['agreement_system']['system_id']}`. Cardinal numerals use base {p['numeral_system']['base']} with `{p['numeral_system']['composition_order']}` composition and cover {p['numeral_system']['range']['minimum']} through {p['numeral_system']['range']['maximum']} compositionally.

## History

The generated synchronic state becomes generation zero. Optional usage, population, transmission, morphology, analogy, and sound-change stages add child nodes with explicit generation numbers and ancestry. A run selects one canonical external sound-change engine and retains its version, rules checksum, forms, and trace.
"""


def export_bundle(state: dict, out_json: str | Path, export_dir: str | Path | None = None) -> dict:
    out = Path(out_json); out.parent.mkdir(parents=True, exist_ok=True)
    root = Path(export_dir) if export_dir else out.with_name(out.stem + "_resources")
    root.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lex_rows = []
    for x in state["lexicon"]:
        display = x.get("display", {})
        lex_rows.append({
            "lexeme_id": x["lexeme_id"], "lemma": x["lemma"], "class": x["class"],
            "concepticon_ids": ";".join(str(m.get("concepticon_id") or "") for m in x.get("concept_mappings", [])),
            "concepts": ";".join(m["concept"] for m in x.get("concept_mappings", [])),
            "phonemic": x["form"], "orthographic": x.get("orthographic", ""),
            "prominence": x["prominence"], "formation": x["formation"],
            "display_en": display.get("en", ""),
            "aliases_en": ";".join(display.get("en_aliases", [])),
            "argument_structure": json.dumps(x.get("argument_structure"), ensure_ascii=False, sort_keys=True) if x.get("argument_structure") else "",
        })
    lex_fields = ["lexeme_id", "lemma", "class", "concepticon_ids", "concepts", "phonemic", "orthographic", "prominence", "formation", "display_en", "aliases_en", "argument_structure"]
    _write_tsv(root / "lexicon.tsv", lex_fields, lex_rows)
    _write_tsv(root / "dictionary.tsv", ["orthographic", "phonemic", "class", "display_en", "aliases_en", "lexeme_id", "concepts", "formation", "argument_structure"], lex_rows)

    reference_rows = []
    numeral_rows = []
    for x in state["lexicon"]:
        if x.get("reference_cell"):
            reference_rows.append({
                "cell_id": x["reference_cell"], "orthographic": x.get("orthographic", ""), "phonemic": x["form"],
                "condition": json.dumps(x.get("grammatical_features", {}), sort_keys=True), "lexeme_id": x["lexeme_id"],
            })
        if x.get("class") == "numeral":
            numeral_rows.append({
                "value": x.get("grammatical_features", {}).get("numeral_value"), "orthographic": x.get("orthographic", ""),
                "phonemic": x["form"], "lexeme_id": x["lexeme_id"],
            })
    _write_tsv(root / "reference.tsv", ["cell_id", "orthographic", "phonemic", "condition", "lexeme_id"], reference_rows)
    _write_tsv(root / "numerals.tsv", ["value", "orthographic", "phonemic", "lexeme_id"], sorted(numeral_rows, key=lambda r: int(r["value"])))
    construction_rows = [{
        "construction_id": c["construction_id"], "name": c["name"],
        "semantic_input": json.dumps(c["semantic_input"], sort_keys=True),
        "relations": ";".join(c["ud"]["relation_ids"]),
    } for c in state["constructions"]]
    _write_tsv(root / "constructions.tsv", ["construction_id", "name", "semantic_input", "relations"], construction_rows)
    _write_tsv(root / "orthography.tsv", ["phoneme", "grapheme"], [{"phoneme": k, "grapheme": v} for k, v in state["orthography"]["segment_symbols"].items()])
    (root / "profile.json").write_text(json.dumps(state["profile"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "semantic_schema.json").write_text(json.dumps(state["semantic_schema"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paradigm_rows = []
    for lid, cells in state["paradigms"].items():
        if lid in {"sample_noun", "sample_verb"}: continue
        for cell in cells:
            paradigm_rows.append({"lexeme_id": lid, "feature_bundle": json.dumps(cell["feature_bundle"], sort_keys=True), "unimorph": cell["unimorph"], "underlying": cell["underlying_form"], "phonemic": cell["form"], "orthographic": cell["orthographic"]})
    _write_tsv(root / "paradigms.tsv", ["lexeme_id", "feature_bundle", "unimorph", "underlying", "phonemic", "orthographic"], paradigm_rows)
    (root / "grammar.md").write_text(render_grammar(state), encoding="utf-8")
    with (root / "examples.igt.txt").open("w", encoding="utf-8") as handle:
        for i, ex in enumerate(state["examples"], 1):
            handle.write(f"[{i}] {ex['construction_id']}\n{ex['interlinear']['phonemic']}\n{ex['interlinear']['gloss']}\n‘{ex['translation']}’\n\n")
    (root / "provenance.json").write_text(json.dumps(state["provenance_graph"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metadata = export_cldf(state, root / "cldf")
    manifest = {}
    for path in sorted([out] + [x for x in root.rglob("*") if x.is_file()]):
        manifest[str(path.relative_to(out.parent))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (root / "checksums.json").write_text(json.dumps({"algorithm": "sha256", "files": manifest}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"json": str(out), "resources": str(root), "cldf_metadata": str(metadata), "files": len(manifest) + 1}
