#!/usr/bin/env python3
"""Rebuild the release checksum ledger over distributable project files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    files = {}
    for path in sorted(x for x in root.rglob("*") if x.is_file()):
        relative = path.relative_to(root)
        if relative.as_posix() == "CHECKSUMS.json" or any(part == "__pycache__" or part.startswith(".") for part in relative.parts) or path.suffix in {".pyc", ".pyo"}:
            continue
        payload = path.read_bytes()
        files[relative.as_posix()] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    target = root / "CHECKSUMS.json"
    target.write_text(json.dumps({"algorithm": "sha256", "file_count": len(files), "files": files}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "file_count": len(files), "out": str(target)}, sort_keys=True))


if __name__ == "__main__":
    main()
