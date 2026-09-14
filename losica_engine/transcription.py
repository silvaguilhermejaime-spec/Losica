from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .config import load_phonology

SCHEMA = "losica-imitation-transcriptions/1"


def inventory_from_config(path: str | Path) -> tuple[str, ...]:
    cfg = load_phonology(path)
    return tuple(cfg.consonants) + tuple(cfg.vowels)


def _parse_tokens(text: str) -> list[str]:
    return [x for x in text.strip().split() if x]


def transcribe_command(wav: Path, command_template: list[str], inventory: set[str]) -> dict:
    command = [part.replace("{wav}", str(wav)) for part in command_template]
    proc = subprocess.run(command, capture_output=True, text=True, check=True)
    raw = _parse_tokens(proc.stdout)
    accepted = raw if raw and all(t in inventory for t in raw) else []
    return {
        "tokens": accepted,
        "status": "accepted" if accepted else "inventory_unresolved",
        "raw_tokens": raw,
        "provenance": {"method": "external_command", "command": command},
    }


def transcribe_allosaurus(wav: Path, inventory: set[str], *, model: str = "uni2005", lang: str = "ipa", emit: float = 1.0) -> dict:
    """Run Allosaurus and classify its emitted phone sequence.

    Sequences whose phones all belong to the configured inventory receive
    ``accepted`` status. Other sequences receive ``inventory_unresolved``. The
    raw recognizer output is preserved for review.
    """
    from allosaurus.app import read_recognizer
    recognizer = read_recognizer(model)
    raw_text = recognizer.recognize(str(wav), lang_id=lang, emit=emit)
    raw = _parse_tokens(raw_text)
    accepted = raw if raw and all(t in inventory for t in raw) else []
    return {
        "tokens": accepted,
        "status": "accepted" if accepted else "inventory_unresolved",
        "raw_tokens": raw,
        "provenance": {
            "method": "allosaurus",
            "model": model,
            "language_inventory": lang,
            "emit": emit,
            "source": "Li et al. 2020 ICASSP; https://github.com/xinjli/allosaurus",
        },
    }


def transcribe_index(index_path: str | Path, *, phonology_path: str | Path, out: str | Path,
                     mode: str, command_template: list[str] | None = None,
                     allosaurus_model: str = "uni2005", allosaurus_lang: str = "ipa", emit: float = 1.0):
    index_path = Path(index_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("schema") != "losica-paired-vocal-imitation-index/1":
        raise ValueError("paired vocal-imitation index required")
    inventory = set(inventory_from_config(phonology_path))
    base = Path(index["dataset"]["dataset_root"])
    rows = []
    for pair in index["pairs"]:
        wav = base / pair["imitation_waveform"]
        if mode == "allosaurus":
            result = transcribe_allosaurus(wav, inventory, model=allosaurus_model, lang=allosaurus_lang, emit=emit)
        elif mode == "command":
            if not command_template:
                raise ValueError("command template required")
            result = transcribe_command(wav, command_template, inventory)
        else:
            raise ValueError("mode must be allosaurus or command")
        rows.append({"imitation_id": pair["imitation_id"], **result})
    payload = {
        "schema": SCHEMA,
        "phonology": str(Path(phonology_path)),
        "inventory": sorted(inventory),
        "records": rows,
    }
    Path(out).write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--phonology", default="config/preproto.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["allosaurus", "command"], required=True)
    ap.add_argument("--command", nargs="+")
    ap.add_argument("--allosaurus-model", default="uni2005")
    ap.add_argument("--allosaurus-lang", default="ipa")
    ap.add_argument("--emit", type=float, default=1.0)
    args = ap.parse_args(argv)
    payload = transcribe_index(args.index, phonology_path=args.phonology, out=args.out, mode=args.mode,
                               command_template=args.command, allosaurus_model=args.allosaurus_model,
                               allosaurus_lang=args.allosaurus_lang, emit=args.emit)
    print(json.dumps({"records": len(payload["records"]), "accepted": sum(r["status"] == "accepted" for r in payload["records"]), "out": args.out}, sort_keys=True))


if __name__ == "__main__":
    main()
