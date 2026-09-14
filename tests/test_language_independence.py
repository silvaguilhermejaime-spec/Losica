import copy
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from losica_engine.display_en import attach_english_display
from losica_engine.full_language import generate_complete_language
from losica_engine.independence import canonical_linguistic_hash
from losica_engine.typology import sample_typological_profile
from tools.build_empirical_core import build_core

ROOT = Path(__file__).resolve().parents[1]
DISPLAY = ROOT / "data" / "display_en_v0_26.json"
SOURCE = ROOT / "data" / "empirical_source_v0_26.json"
CORE = ROOT / "data" / "empirical_core_v0_26.json"


def _scrambled_display(tmp_path: Path) -> Path:
    obj = json.loads(DISPLAY.read_text(encoding="utf-8"))
    for i, row in enumerate(obj["concepts"]):
        for key in ("gloss", "definition", "semantic_field", "ontological_category"):
            if key in row:
                row[key] = f"X{i:04d}:{key}"
    path = tmp_path / "display-randomized.json"
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return path


def test_display_locales_preserve_canonical_language(tmp_path):
    core = generate_complete_language(seed=19020, vocabulary_scale="core", display_locale=None)
    normal = copy.deepcopy(core); randomized = copy.deepcopy(core)
    attach_english_display(normal["lexicon"])
    attach_english_display(randomized["lexicon"], _scrambled_display(tmp_path))
    assert canonical_linguistic_hash(core) == canonical_linguistic_hash(normal) == canonical_linguistic_hash(randomized)


def test_core_generation_runs_with_english_adapter_blocked():
    code = r'''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {"losica_engine.display_en", "losica_engine.translation"}:
            raise ImportError("adapter blocked")
        return None
sys.meta_path.insert(0, Block())
from losica_engine.full_language import generate_complete_language
from losica_engine.independence import canonical_linguistic_hash
state = generate_complete_language(seed=19020, vocabulary_scale="core", display_locale=None)
print(canonical_linguistic_hash(state))
'''
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    expected = canonical_linguistic_hash(generate_complete_language(seed=19020, vocabulary_scale="core", display_locale=None))
    assert proc.stdout.strip() == expected


def test_structural_source_rebuilds_core_exactly():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    expected = json.loads(CORE.read_text(encoding="utf-8"))
    assert build_core(source) == expected


def test_structural_source_projects_only_machine_fields():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    concepts = source["semantic_probe_registry"]["concepts"]
    assert len(concepts) == 512
    assert len({row["community_id"] for row in concepts}) > 100
    assert all(set(row) <= {"concepticon_id", "network_rank", "community_id", "form_count", "variety_count", "language_count", "family_count", "graph_degree", "weighted_family_degree", "weighted_language_degree"} for row in concepts)


def test_preprocessing_human_annotations_are_projection_invariant():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    decorated = copy.deepcopy(source)
    for i, row in enumerate(decorated["semantic_probe_registry"]["concepts"]):
        row.update({"gloss": f"WORD_{i}", "definition": f"TEXT_{i}", "semantic_field": f"FIELD_{i}"})
    for edge in decorated["colexification_edges"]:
        edge.update({"source_gloss": "A", "target_gloss": "B"})
    assert build_core(source) == build_core(decorated)


def test_pre_generation_annotation_scramble_preserves_language(tmp_path):
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    decorated = copy.deepcopy(source)
    for i, row in enumerate(decorated["semantic_probe_registry"]["concepts"]):
        row.update({"gloss": f"X{i}", "definition": f"Y{i}", "semantic_field": f"Z{i}"})
    for edge in decorated["colexification_edges"]:
        edge.update({"source_gloss": "X", "target_gloss": "Y"})
    a_path = tmp_path / "core-a.json"
    b_path = tmp_path / "core-b.json"
    a_path.write_text(json.dumps(build_core(source)), encoding="utf-8")
    b_path.write_text(json.dumps(build_core(decorated)), encoding="utf-8")
    a = generate_complete_language(seed=19020, vocabulary_scale="core", display_locale=None, empirical_snapshot_path=a_path)
    b = generate_complete_language(seed=19020, vocabulary_scale="core", display_locale=None, empirical_snapshot_path=b_path)
    assert canonical_linguistic_hash(a) == canonical_linguistic_hash(b)


def test_generation_code_uses_structural_probe_interface():
    paths = [ROOT / "losica_engine/semantic_network.py", ROOT / "losica_engine/lexicon_v021.py", ROOT / "tools/build_empirical_core.py"]
    text = "\n".join(p.read_text(encoding="utf-8") for p in paths)
    assert re.search(r"\bC_[0-9]+\b", text) is None
    for token in ("REQUIRED_GLOSSES", "CONCEPTICON_GLOSS", "Concepticon_Gloss", "Source_Concept", "Target_Concept", "PART_OF_SPEECH", "FRAME_INTR", "FRAME_DITR", "FRAME_CONTENT"):
        assert token not in text


def test_generated_vocabulary_has_internal_many_to_many_semantics():
    state = generate_complete_language(seed=19020, vocabulary_scale="large", display_locale=None)
    roots = [x for x in state["lexicon"] if x.get("formation") == "semantic_region_lexicalization"]
    assert roots
    assert all(x["concept"] == x["semantic_region_id"] and x["concept"].startswith("sr:") for x in roots)
    assert any(len(x["concept_mappings"]) > 1 for x in roots)
    counts = Counter(m["probe_id"] for x in roots for m in x["concept_mappings"])
    assert len(counts) == 512
    assert any(value > 1 for value in counts.values())
    assert len(roots) < len(counts)


def test_probe_membership_changes_with_seed():
    a = generate_complete_language(seed=19020, vocabulary_scale="core", display_locale=None)
    b = generate_complete_language(seed=19021, vocabulary_scale="core", display_locale=None)
    a_probes = {m["probe_id"] for x in a["lexicon"] for m in x.get("concept_mappings", [])}
    b_probes = {m["probe_id"] for x in b["lexicon"] for m in x.get("concept_mappings", [])}
    assert a_probes != b_probes


def test_reference_architecture_varies_by_seed():
    plain = sample_typological_profile(1)
    clusive = sample_typological_profile(3)
    dual_clusive = sample_typological_profile(8)
    assert plain["reference_system"]["system_id"] == "REF-A"
    assert clusive["reference_system"]["system_id"] == "REF-B"
    assert dual_clusive["reference_system"]["system_id"] == "REF-C"


def test_canonical_generation_is_independent_of_display_file_existence():
    baseline = generate_complete_language(seed=19020, vocabulary_scale="core", display_locale=None)
    renamed = DISPLAY.with_suffix(".hidden")
    DISPLAY.rename(renamed)
    try:
        again = generate_complete_language(seed=19020, vocabulary_scale="core", display_locale=None)
    finally:
        renamed.rename(DISPLAY)
    assert canonical_linguistic_hash(baseline) == canonical_linguistic_hash(again)
