"""Usage-driven fusion and synchronic lexical reanalysis."""
from __future__ import annotations


def _reduce_fusion(left: str, right: str) -> tuple[str, str]:
    fused = (left + right).replace(".", "").replace("-", "")
    collapsed = "".join(ch for index, ch in enumerate(fused) if index == 0 or ch != fused[index - 1])
    if len(collapsed) > 8:
        reduced = collapsed[:4] + collapsed[-3:]
    else:
        reduced = collapsed
    return fused, reduced


def lexicalize_constructions(constructions: list[dict], root_lexicon: list[dict], *, limit: int = 16) -> tuple[list[dict], dict]:
    """Store frequent constructions as new roots while retaining historical proof."""
    roots = {row["semantic_region_id"]: row for row in root_lexicon}
    selected = sorted(
        (row for row in constructions if row["train_event_count"] >= 8 and row["holdout_event_count"] >= 3),
        key=lambda row: (-row["train_event_count"], row["construction_id"]),
    )[:limit]
    lexemes, transitions = [], []
    used_forms = {row["orthographic"] for row in root_lexicon}
    for index, construction in enumerate(selected, 1):
        left, right = (roots[region_id] for region_id in construction["ordered_regions"])
        fused, reduced = _reduce_fusion(left["orthographic"], right["orthographic"])
        while reduced in used_forms:
            reduced += "a"
        used_forms.add(reduced)
        lexeme_id = f"lx:h{index:04d}"
        root_id = f"root:h{index:04d}"
        region_id = f"sr:h{index:04d}"
        transition = {
            "transition_id": f"hr:{index:04d}",
            "construction_id": construction["construction_id"],
            "source_lexeme_ids": [left["lexeme_id"], right["lexeme_id"]],
            "source_region_ids": list(construction["ordered_regions"]),
            "stages": [
                {"generation": 0, "analysis": [left["lexeme_id"], right["lexeme_id"]], "form": left["orthographic"] + " " + right["orthographic"], "productivity": "productive"},
                {"generation": 1, "analysis": [left["lexeme_id"], right["lexeme_id"]], "form": fused, "productivity": "restricted"},
                {"generation": 2, "analysis": [root_id], "form": reduced, "productivity": "stored_root"},
            ],
            "trigger": {
                "train_token_count": construction["train_event_count"],
                "holdout_token_count": construction["holdout_event_count"],
                "rule": "construction occurs in at least 8 training events and 3 held-out events",
            },
            "current_boundary_visible": False,
            "source_process_productive": False,
        }
        transitions.append(transition)
        lexemes.append({
            "lexeme_id": lexeme_id,
            "semantic_region_id": region_id,
            "form": reduced,
            "orthographic": reduced,
            "syllables": [reduced],
            "prominence": 0,
            "annotated_form": "ˈ" + reduced,
            "formation": "historical_lexicalization",
            "current_analysis": {"root_id": root_id, "parts": [root_id]},
            "historical_analysis": {
                "source_lexeme_ids": [left["lexeme_id"], right["lexeme_id"]],
                "source_region_ids": list(construction["ordered_regions"]),
                "construction_id": construction["construction_id"],
                "transition_id": transition["transition_id"],
            },
            "distribution": {
                "distribution_class_id": "dc:historical-root",
                "licensed_construction_id": construction["construction_id"],
                "participant_slots": [],
            },
            "generation_trace": {
                "algorithm_id": "usage-fusion-reanalysis-v1",
                "transition_id": transition["transition_id"],
                "input_event_ids": construction["train_event_ids"],
            },
        })
    return lexemes, {
        "schema": "losica-causal-history/1",
        "current_generation": 2,
        "transitions": transitions,
    }
