"""Version-preserving importers for Losica's separately distributed evidence."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(64 * 1024 * 1024)


def _rows(path: Path, delimiter=","):
    with path.open(encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle, delimiter=delimiter)


def import_grambank(cldf_dir: str | Path, parameter_ids: set[str] | None = None, *, version="1.0") -> dict:
    root = Path(cldf_dir)
    params = {r["ID"]: r for r in _rows(root / "parameters.csv") if parameter_ids is None or r["ID"] in parameter_ids}
    languages = {r["ID"]: r for r in _rows(root / "languages.csv")}
    observations = []
    for r in _rows(root / "values.csv"):
        if r["Parameter_ID"] in params:
            lang = languages[r["Language_ID"]]
            observations.append({
                "observation_id": r["ID"], "parameter_id": r["Parameter_ID"], "value": r["Value"] if r["Value"] != "?" else None,
                "missing": r["Value"] == "?", "language_id": r["Language_ID"], "family": lang.get("Family_name"),
                "macroarea": lang.get("Macroarea"), "latitude": lang.get("Latitude"), "longitude": lang.get("Longitude"), "source": r.get("Source"),
            })
    return {"schema": "losica-grambank-import/1", "source": "Grambank", "version": version, "parameters": params, "observations": observations, "missing_data_preserved": True}


def import_wals(cldf_dir: str | Path, feature_ids: set[str] | None = None, *, version="2020.4") -> dict:
    root = Path(cldf_dir)
    params = {r["ID"]: {"ID": r["ID"], "Chapter_ID": r.get("Chapter_ID")} for r in _rows(root / "parameters.csv") if feature_ids is None or r["ID"] in feature_ids}
    codes_path = root / "codes.csv"
    codes = {r["ID"]: r.get("Name") or r.get("Description") for r in _rows(codes_path)} if codes_path.exists() else {}
    languages = {r["ID"]: r for r in _rows(root / "languages.csv")}
    observations = []
    for r in _rows(root / "values.csv"):
        if r["Parameter_ID"] in params:
            lang = languages[r["Language_ID"]]
            observations.append({
                "observation_id": r["ID"], "feature_id": r["Parameter_ID"], "code_id": r.get("Code_ID"),
                "value": codes.get(r.get("Code_ID")) or r.get("Value"),
                "source_value": r.get("Value"), "language_id": r["Language_ID"], "family_id": lang.get("Family"),
                "genus_id": lang.get("Genus"), "macroarea_id": lang.get("Macroarea"), "source_id": r.get("Source"),
            })
    return {"schema": "losica-wals-structural-import/2", "source": "WALS Online", "version": version, "features": params, "observations": observations}

def import_unimorph(path: str | Path, *, dataset_id="unspecified", version="current") -> dict:
    records = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip() or line.startswith("#"):
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 3:
                raise ValueError(f"UniMorph line {line_no} requires lemma, form, and feature bundle")
            features = [x for x in cols[2].split(";") if x]
            records.append({"record_id": f"{dataset_id}:{line_no}", "lemma": cols[0], "form": cols[1], "feature_bundle": features, "segmentation": cols[3] if len(cols) > 3 else None})
    return {"schema": "losica-unimorph-import/1", "source": "UniMorph", "version": version, "dataset_id": dataset_id, "records": records}


def import_concepticon(path: str | Path, *, version="3.4.0") -> dict:
    records = []
    for r in _rows(Path(path), "\t"):
        records.append({"concepticon_id": r["ID"], "gloss": r["GLOSS"], "definition": r.get("DEFINITION"), "semantic_field": r.get("SEMANTICFIELD"), "ontological_category": r.get("ONTOLOGICAL_CATEGORY"), "replacement_id": r.get("REPLACEMENT_ID") or None})
    return {"schema": "losica-concepticon-import/1", "source": "Concepticon", "version": version, "records": records}


def _zip_rows(path: Path):
    with zipfile.ZipFile(path) as zf:
        names = [x for x in zf.namelist() if x.endswith(".csv")]
        if len(names) != 1:
            raise ValueError("CLICS archive requires exactly one CSV member")
        with zf.open(names[0]) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"))


def import_clics(path: str | Path, *, version="1.0", minimum_languages=1) -> dict:
    """Import CLICS through CLDF ID references and multilingual form identity."""
    root = Path(path)
    if root.is_file():
        edges = []
        for row in _rows(root):
            language_count = int(row.get("Language_Count") or row.get("language_count") or 0)
            if language_count < minimum_languages:
                continue
            edges.append({
                "edge_id": row.get("ID") or row.get("edge_id"),
                "source_concepticon_id": row.get("Source_Concept") or row.get("source_concepticon_id"),
                "target_concepticon_id": row.get("Target_Concept") or row.get("target_concepticon_id"),
                "form_count": int(row.get("Form_Count") or row.get("form_count") or 0),
                "variety_count": int(row.get("Variety_Count") or row.get("variety_count") or 0),
                "language_count": language_count,
                "family_count": int(row.get("Family_Count") or row.get("family_count") or 0),
                "family_weight": float(row.get("Family_Weight") or row.get("family_weight") or 0.0),
            })
        return {
            "schema": "losica-clics-edge-import/1", "source": "CLICS4", "version": version,
            "probe_count": len({value for edge in edges for value in (edge["source_concepticon_id"], edge["target_concepticon_id"])}),
            "edges": edges,
        }
    cldf = root / "cldf" if (root / "cldf").is_dir() else root
    concept_path = cldf / "concepts.csv.zip"
    form_path = cldf / "forms.csv.zip"
    if not concept_path.exists() or not form_path.exists():
        raise ValueError("CLICS CLDF concepts.csv.zip and forms.csv.zip required")
    param_to_probe = {}
    for r in _zip_rows(concept_path):
        cid = (r.get("Concepticon_ID") or "").strip()
        if cid:
            param_to_probe[r["ID"]] = cid
    lang_path = cldf / "languages.csv"
    languages = {r["ID"]: r for r in _rows(lang_path)} if lang_path.exists() else {}
    buckets = defaultdict(set)
    for r in _zip_rows(form_path):
        cid = param_to_probe.get(r["Parameter_ID"])
        form = (r.get("Form") or "").strip()
        if cid and form:
            buckets[(r["Language_ID"], form)].add(cid)
    evidence = defaultdict(lambda: {"forms": set(), "varieties": set(), "languages": set(), "families": set()})
    for (variety, form), cids in buckets.items():
        if len(cids) < 2:
            continue
        meta = languages.get(variety, {})
        language = meta.get("Glottocode") or variety
        family = meta.get("Family") or meta.get("Family_Name") or ""
        for a, b in __import__("itertools").combinations(sorted(cids, key=int), 2):
            rec = evidence[(a, b)]
            rec["forms"].add((variety, form)); rec["varieties"].add(variety); rec["languages"].add(language)
            if family: rec["families"].add(family)
    edges = []
    for (a, b), ev in evidence.items():
        if len(ev["languages"]) >= minimum_languages:
            edges.append({
                "edge_id": f"{a}-{b}", "source_concepticon_id": a, "target_concepticon_id": b,
                "form_count": len(ev["forms"]), "variety_count": len(ev["varieties"]),
                "language_count": len(ev["languages"]), "family_count": len(ev["families"]),
                "family_weight": float(len(ev["families"])),
            })
    edges.sort(key=lambda r: (-r["family_count"], -r["language_count"], r["edge_id"]))
    return {"schema": "losica-clics-structural-import/2", "source": "CLICS4", "version": version, "probe_count": len(set(param_to_probe.values())), "edges": edges}

def import_phoible(path: str | Path, *, version="2.0") -> dict:
    inventories, segments = defaultdict(set), {}
    for r in _rows(Path(path)):
        inventories[r["InventoryID"]].add(r["Phoneme"])
        features = {k: v for k, v in r.items() if k not in {"InventoryID", "Glottocode", "ISO6393", "LanguageName", "SpecificDialect", "GlyphID", "Phoneme", "Allophones", "Marginal", "SegmentClass", "Source"}}
        segments.setdefault(r["Phoneme"], {"segment": r["Phoneme"], "class": r.get("SegmentClass"), "features": features})
    return {"schema": "losica-phoible-import/1", "source": "PHOIBLE", "version": version, "inventory_count": len(inventories), "segment_types": segments, "inventories": {k: sorted(v) for k, v in inventories.items()}}


def import_conllu(path: str | Path, *, treebank_id: str, ud_version="2.18") -> dict:
    sentences, comments, tokens = [], {}, []
    with Path(path).open(encoding="utf-8") as handle:
        for line in list(handle) + ["\n"]:
            line = line.rstrip("\n")
            if not line:
                if tokens:
                    sid = comments.get("sent_id", f"{treebank_id}:{len(sentences)+1}")
                    sentences.append({"sentence_id": sid, "text": comments.get("text"), "tokens": tokens, "relations": sorted({t["deprel"] for t in tokens})})
                comments, tokens = {}, []
            elif line.startswith("#"):
                if "=" in line:
                    key, value = line[1:].split("=", 1); comments[key.strip()] = value.strip()
            else:
                cols = line.split("\t")
                if len(cols) != 10:
                    raise ValueError(f"CoNLL-U row requires 10 columns: {line!r}")
                if "-" in cols[0] or "." in cols[0]:
                    continue
                tokens.append({"id": int(cols[0]), "form": cols[1], "lemma": cols[2], "upos": cols[3], "xpos": cols[4], "feats": cols[5], "head": int(cols[6]), "deprel": cols[7], "deps": cols[8], "misc": cols[9]})
    return {"schema": "losica-ud-import/1", "source": "Universal Dependencies", "version": ud_version, "treebank_id": treebank_id, "sentences": sentences}


def extract_ud_templates(imported: dict, required_relations: set[str] | None = None) -> list[dict]:
    out = []
    for sentence in imported["sentences"]:
        relations = set(sentence["relations"])
        if required_relations is None or required_relations <= relations:
            roots = [t for t in sentence["tokens"] if t["head"] == 0]
            out.append({"template_id": f"{imported['treebank_id']}:{sentence['sentence_id']}", "source_treebank": imported["treebank_id"], "source_sentence_id": sentence["sentence_id"], "root_upos": roots[0]["upos"] if roots else None, "relations": sorted(relations), "dependencies": [{"id": t["id"], "head": t["head"], "deprel": t["deprel"]} for t in sentence["tokens"]]})
    return out


def import_paired_audio_manifest(path: str | Path, *, corpus: str, version: str, field_map: dict[str, str]) -> dict:
    records = []
    for line_no, r in enumerate(_rows(Path(path)), 2):
        mapped = {target: r.get(source) for target, source in field_map.items()}
        mapped["record_id"] = mapped.get("record_id") or f"{corpus}:{line_no}"
        records.append(mapped)
    return {"schema": "losica-paired-vocal-imitation-import/1", "source": corpus, "version": version, "records": records}


def import_esc50_voice(path: str | Path, *, version="1") -> dict:
    return import_paired_audio_manifest(path, corpus="ESC-50-Voice", version=version, field_map={"record_id": "id", "reference_wav": "reference_wav", "imitation_wav": "imitation_wav", "speaker_id": "speaker_id", "paired_source_id": "source_id"})


def import_vocalsketch(path: str | Path, *, version="2015") -> dict:
    return import_paired_audio_manifest(path, corpus="VocalSketch", version=version, field_map={"record_id": "id", "referent_sound": "referent", "participant_id": "participant", "response": "response", "identified_as": "identified_as", "correct": "correct"})


def import_vocal_imitation_set(path: str | Path, *, version="2018") -> dict:
    return import_paired_audio_manifest(path, corpus="Vocal Imitation Set", version=version, field_map={"record_id": "id", "sound_class": "class", "reference_wav": "reference", "imitation_wav": "imitation", "speaker_id": "speaker"})


def bind_qbv_ranking(ranking_path: str | Path, query_wav: str | Path, *, checkpoint_id: str, corpus_index_id: str, preprocessing: dict) -> dict:
    query = Path(query_wav)
    digest = hashlib.sha256(query.read_bytes()).hexdigest()
    obj = json.loads(Path(ranking_path).read_text(encoding="utf-8"))
    if obj.get("schema") != "losica-vocal-retrieval-ranking/1":
        raise ValueError("losica-vocal-retrieval-ranking/1 required")
    unique, seen = [], set()
    for row in obj["ranking"]:
        key = (digest, row["imitation_id"], row.get("speaker_id", ""))
        if key not in seen:
            seen.add(key); unique.append({**row, "query_wav_sha256": digest})
    return {"schema": "losica-bound-qbv-ranking/1", "query_wav_sha256": digest, "checkpoint_id": checkpoint_id, "corpus_index_id": corpus_index_id, "preprocessing": preprocessing, "ranking": unique, "duplicate_records_removed": len(obj["ranking"]) - len(unique)}


def import_allosaurus_hypotheses(path: str | Path, *, model_id: str) -> dict:
    hypotheses = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip(): continue
        cols = line.split("\t")
        hypotheses.append({"hypothesis_id": f"{model_id}:{line_no}", "phones": cols[0].split(), "score": float(cols[1]) if len(cols) > 1 else None})
    return {"schema": "losica-allosaurus-import/1", "source": "Allosaurus", "model_id": model_id, "hypotheses": hypotheses, "uncertainty_retained": len(hypotheses) > 1}
