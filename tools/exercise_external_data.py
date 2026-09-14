#!/usr/bin/env python3
"""Exercise full pinned upstream files and emit machine-readable counts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from losica_engine.importers import import_clics, import_concepticon, import_grambank, import_phoible, import_wals


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--grambank", required=True, help="Grambank CLDF directory")
    ap.add_argument("--wals", required=True, help="WALS CLDF directory")
    ap.add_argument("--concepticon", required=True, help="concepticon.tsv")
    ap.add_argument("--clics", required=True, help="colexifications.csv or .zip")
    ap.add_argument("--phoible", required=True, help="phoible.csv")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    grambank = import_grambank(args.grambank)
    wals = import_wals(args.wals, {"20A", "21A", "22A", "23A", "24A", "25A", "49A", "81A", "85A", "86A", "87A", "89A", "101A", "102A"})
    concepticon = import_concepticon(args.concepticon)
    clics = import_clics(args.clics)
    phoible = import_phoible(args.phoible)
    report = {
        "schema": "losica-external-data-exercise/1",
        "status": "PASS",
        "components": {
            "Grambank": {"version": grambank["version"], "parameters": len(grambank["parameters"]), "observations": len(grambank["observations"]), "missing_observations": sum(x["missing"] for x in grambank["observations"])},
            "WALS Online": {"version": wals["version"], "features": len(wals["features"]), "observations": len(wals["observations"])},
            "Concepticon": {"version": concepticon["version"], "concepts": len(concepticon["records"])},
            "CLICS4": {"version": clics["version"], "edges": len(clics["edges"])},
            "PHOIBLE": {"version": phoible["version"], "inventories": phoible["inventory_count"], "segment_types": len(phoible["segment_types"])},
        },
        "inputs": {k: str(Path(v).resolve()) for k, v in {"grambank": args.grambank, "wals": args.wals, "concepticon": args.concepticon, "clics": args.clics, "phoible": args.phoible}.items()},
    }
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["components"], sort_keys=True))


if __name__ == "__main__":
    main()
