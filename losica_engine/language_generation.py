from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from .config import load_phonology
from .grammar_evolution import active_affixes, infer_marker_states, realize
from .phonology import syllabify_surface
from .sound_change_external import apply_external_sound_change, load_integration_config
from .usage_history import UsageEvent, load_usage_events

SCHEMA = "losica-generated-language/3"
DEFAULT_PHONOLOGY = Path(__file__).resolve().parents[1] / "config" / "preproto.json"


def load_lexicon_rows(path: str | Path) -> dict[str, dict]:
    p = Path(path)
    out = {}
    with p.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        required = {"lexeme_id", "category_id", "preproto_form", "prominence", "provenance"}
        if not required <= set(r.fieldnames or []):
            raise ValueError(f"lexicon requires columns {sorted(required)}")
        for line_no, row in enumerate(r, 2):
            lid = (row.get("lexeme_id") or "").strip()
            if not lid:
                continue
            if lid in out:
                raise ValueError(f"duplicate lexeme_id {lid!r} at line {line_no}")
            out[lid] = {
                "lexeme_id": lid,
                "category_id": row["category_id"],
                "preproto_form": row["preproto_form"],
                "prominence": int(row["prominence"]),
                "provenance": row.get("provenance", ""),
            }
    return out


def load_pathway_registry(path: str | Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if obj.get("schema") != "losica-grammaticalization-registry/2":
        raise ValueError("losica-grammaticalization-registry/2 required")
    return {r["id"]: r for r in obj.get("paths", [])}


def _latest_rows_for_state(events: list[UsageEvent], state) -> list[UsageEvent]:
    return [
        e for e in events
        if e.marker_lexeme_id == state.marker_lexeme_id
        and e.function_id == state.function_id
        and e.generation == state.generation_last
    ]


def _current_allomorphs(events: list[UsageEvent], state) -> list[str]:
    return sorted({e.marker_form for e in _latest_rows_for_state(events, state)})


def _state_json(state, lexicon, pathways, events):
    source = lexicon[state.marker_lexeme_id]
    path_records = [pathways[x] for x in state.pathway_ids if x in pathways]
    return {
        "marker_lexeme_id": state.marker_lexeme_id,
        "source_lexical_form": source["preproto_form"],
        "function_id": state.function_id,
        "attachment": state.attachment,
        "order": state.order,
        "position": state.position,
        "current_form": state.form,
        "current_allomorphs": _current_allomorphs(events, state),
        "token_frequency": state.token_frequency,
        "host_type_count": state.host_type_count,
        "construction_type_count": state.construction_type_count,
        "generation_first": state.generation_first,
        "generation_last": state.generation_last,
        "observed_forms": list(state.observed_forms),
        "evidence_event_ids": list(state.evidence_event_ids),
        "pathways": path_records,
    }


def _host_current_affix_forms(events: list[UsageEvent], states) -> dict[tuple[str, str, str], dict]:
    """Return current host-conditioned affix forms from the chronology.

    Selection uses events at the marker state's current generation. Competing
    forms for one host are resolved by token frequency, then lexical order for
    reproducibility.
    """
    current_generation = {
        (s.marker_lexeme_id, s.function_id): s.generation_last
        for s in states if s.attachment == "affix"
    }
    grouped: dict[tuple[str, str, str], list[UsageEvent]] = defaultdict(list)
    for e in events:
        key = (e.marker_lexeme_id, e.function_id)
        if e.attachment != "affix" or current_generation.get(key) != e.generation:
            continue
        grouped[(e.host_lexeme_id, e.marker_lexeme_id, e.function_id)].append(e)

    out = {}
    for key, rows in grouped.items():
        counts = Counter()
        ids_by_form = defaultdict(list)
        for e in rows:
            counts[e.marker_form] += e.count
            ids_by_form[e.marker_form].append(e.event_id)
        form = max(counts, key=lambda x: (counts[x], x))
        out[key] = {
            "form": form,
            "event_ids": sorted(ids_by_form[form]),
            "count": counts[form],
        }
    return out


def _canonical_preproto(surface: str, cfg) -> str:
    return ".".join(syllabify_surface(surface, cfg))


def _validate_lexicon_phonotactics(lexicon: dict[str, dict], cfg) -> None:
    for lid, row in lexicon.items():
        try:
            _canonical_preproto(row["preproto_form"].replace(".", ""), cfg)
        except ValueError as exc:
            raise ValueError(
                f"lexeme {lid!r} has phonotactically illegal Pre-Proto form "
                f"{row['preproto_form']!r}: {exc}"
            ) from exc


def _validate_current_affix_events(events: list[UsageEvent], states, lexicon, cfg) -> None:
    current_generation = {
        (s.marker_lexeme_id, s.function_id): s.generation_last
        for s in states if s.attachment == "affix"
    }
    for e in events:
        key = (e.marker_lexeme_id, e.function_id)
        if e.attachment != "affix" or current_generation.get(key) != e.generation:
            continue
        stem = lexicon[e.host_lexeme_id]["preproto_form"].replace(".", "")
        marker = e.marker_form.replace(".", "")
        surface = marker + stem if e.order == "before" else stem + marker
        try:
            _canonical_preproto(surface, cfg)
        except ValueError as exc:
            raise ValueError(
                f"current affix event {e.event_id!r} produces phonotactically illegal "
                f"form {surface!r} from marker {e.marker_form!r} and host "
                f"{lexicon[e.host_lexeme_id]['preproto_form']!r}; record an attested "
                f"legal allomorph or a historical phonological derivation"
            ) from exc


def generate_language(
    *,
    lexicon_path: str | Path,
    usage_path: str | Path,
    pathway_registry_path: str | Path | None = None,
    phonology_path: str | Path = DEFAULT_PHONOLOGY,
    sound_rules_path: str | Path | None = None,
    sound_command: list[str] | str | None = None,
    sound_contract: str = "lexurgy",
) -> dict:
    lexicon = load_lexicon_rows(lexicon_path)
    events = load_usage_events(usage_path)
    pathways = load_pathway_registry(pathway_registry_path)
    phonology = load_phonology(phonology_path)

    missing = sorted(({e.host_lexeme_id for e in events} | {e.marker_lexeme_id for e in events}) - set(lexicon))
    if missing:
        raise ValueError("usage history references unknown lexemes: " + ", ".join(missing))

    unknown_paths = sorted({e.pathway_id for e in events if e.pathway_id and e.pathway_id not in pathways})
    if unknown_paths:
        raise ValueError("usage history references unknown pathway IDs: " + ", ".join(unknown_paths))

    _validate_lexicon_phonotactics(lexicon, phonology)
    states = infer_marker_states(events)
    affixes = active_affixes(states)
    _validate_current_affix_events(events, states, lexicon, phonology)

    # Current productive examples use only host-conditioned forms actually
    # attested at the marker state's latest generation.
    current_host_forms = _host_current_affix_forms(events, states)
    by_state = {(s.marker_lexeme_id, s.function_id): s for s in states}
    host_states = defaultdict(list)
    for (host_id, marker_id, function_id), evidence in current_host_forms.items():
        state = by_state[(marker_id, function_id)]
        host_states[host_id].append((state, evidence))

    examples = []
    for host_id in sorted(host_states):
        stem = lexicon[host_id]["preproto_form"]
        applicable = sorted(host_states[host_id], key=lambda x: x[0].position)
        for state, evidence in applicable:
            overrides = {(state.marker_lexeme_id, state.function_id): evidence["form"]}
            raw = realize(stem, [state], overrides)
            examples.append({
                "host_lexeme_id": host_id,
                "function_ids": [state.function_id],
                "marker_lexeme_ids": [state.marker_lexeme_id],
                "marker_forms": [evidence["form"]],
                "evidence_event_ids": evidence["event_ids"],
                "preproto_form": _canonical_preproto(raw, phonology),
            })

        if len(applicable) > 1:
            states_for_host = [x[0] for x in applicable]
            overrides = {
                (state.marker_lexeme_id, state.function_id): evidence["form"]
                for state, evidence in applicable
            }
            raw = realize(stem, states_for_host, overrides)
            try:
                canonical = _canonical_preproto(raw, phonology)
            except ValueError as exc:
                markers = ", ".join(overrides.values())
                raise ValueError(
                    f"productive affix stack on host {host_id!r} is phonotactically illegal: "
                    f"{raw!r} from current attested marker forms [{markers}]"
                ) from exc
            examples.append({
                "host_lexeme_id": host_id,
                "function_ids": [s.function_id for s in states_for_host],
                "marker_lexeme_ids": [s.marker_lexeme_id for s in states_for_host],
                "marker_forms": [overrides[(s.marker_lexeme_id, s.function_id)] for s in states_for_host],
                "evidence_event_ids": sorted(
                    event_id for _, evidence in applicable for event_id in evidence["event_ids"]
                ),
                "preproto_form": canonical,
            })

    historical_engine = None
    if sound_command is not None:
        if sound_rules_path is None:
            raise ValueError("sound_rules_path required when sound_command is supplied")
        transformed = apply_external_sound_change(
            [x["preproto_form"] for x in examples],
            rules_path=sound_rules_path,
            command=sound_command,
            command_contract=sound_contract,
        )
        for row, form in zip(examples, transformed):
            row["historical_form"] = form
        historical_engine = {
            "command": sound_command if isinstance(sound_command, str) else list(sound_command),
            "rules": str(sound_rules_path),
            "contract": sound_contract,
        }

    return {
        "schema": SCHEMA,
        "lexicon": list(lexicon.values()),
        "usage_event_count": len(events),
        "marker_states": [_state_json(s, lexicon, pathways, events) for s in states],
        "productive_affixes": [_state_json(s, lexicon, pathways, events) for s in affixes],
        "phonotactics": {
            "language": phonology.language_metadata,
            "syllable": phonology.syllable,
            "onsets": list(phonology.onsets),
            "vowels": list(phonology.vowels),
            "codas": list(phonology.codas),
            "realization_policy": "attested current allomorph + legal syllabification",
        },
        "morphotactics": {
            "source": "current observed affix positions",
            "positions": [
                {
                    "function_id": s.function_id,
                    "marker_lexeme_id": s.marker_lexeme_id,
                    "position": s.position,
                    "order": s.order,
                }
                for s in sorted(affixes, key=lambda x: x.position)
            ],
        },
        "generated_forms": examples,
        "historical_engine": historical_engine,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate current Losica morphology from lexicon + usage history")
    ap.add_argument("--lexicon", default="data/lexicon.tsv")
    ap.add_argument("--usage", default="data/usage_events.jsonl")
    ap.add_argument("--pathways", default="config/grammaticalization_registry.json")
    ap.add_argument("--phonology", default="config/preproto.json")
    ap.add_argument("--out", default="generated_language.json")
    ap.add_argument("--integrations", default="config/integrations.json")
    ap.add_argument("--apply-sound-change", action="store_true")
    ap.add_argument("--sound-command")
    ap.add_argument("--sound-rules")
    ap.add_argument("--sound-contract", choices=["lexurgy", "generic"], default="lexurgy")
    args = ap.parse_args(argv)

    sound_command = args.sound_command
    sound_rules = args.sound_rules
    sound_contract = args.sound_contract
    if args.apply_sound_change and not sound_command:
        cfg = load_integration_config(args.integrations)
        sc = cfg["sound_change"]
        sound_command = sc["command"]
        sound_rules = sc["rules"]
        sound_contract = sc.get("contract", "lexurgy")

    obj = generate_language(
        lexicon_path=args.lexicon,
        usage_path=args.usage,
        pathway_registry_path=args.pathways,
        phonology_path=args.phonology,
        sound_rules_path=sound_rules if args.apply_sound_change else None,
        sound_command=sound_command if args.apply_sound_change else None,
        sound_contract=sound_contract,
    )
    Path(args.out).write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": args.out,
        "lexemes": len(obj["lexicon"]),
        "usage_events": obj["usage_event_count"],
        "productive_affixes": len(obj["productive_affixes"]),
        "generated_forms": len(obj["generated_forms"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
