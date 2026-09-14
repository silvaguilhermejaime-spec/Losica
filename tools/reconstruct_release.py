#!/usr/bin/env python3
"""Reconstruct and verify the complete Losica release from tracked parts."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "release"
PARTS_DIR = RELEASE_DIR / "losica-0.29-causal-with-external-sources.zip.parts"
CHECKSUMS = RELEASE_DIR / "SHA256SUMS"
ARCHIVE_NAME = "losica-0.29-causal-with-external-sources.zip"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def expected_checksums() -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        checksum, relative = line.split(maxsplit=1)
        checksums[relative.strip()] = checksum
    return checksums


def reconstruct(target: Path) -> None:
    checksums = expected_checksums()
    parts = sorted(PARTS_DIR.glob("part-*"))
    if not parts:
        raise SystemExit(f"no release parts found in {PARTS_DIR}")

    for part in parts:
        relative = part.relative_to(ROOT).as_posix()
        expected = checksums.get(relative)
        actual = digest(part)
        if expected is None or actual != expected:
            raise SystemExit(f"checksum mismatch: {relative}")

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("wb") as output:
        for part in parts:
            with part.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(block)

    expected_archive = checksums[ARCHIVE_NAME]
    actual_archive = digest(temporary)
    if actual_archive != expected_archive:
        temporary.unlink(missing_ok=True)
        raise SystemExit(f"archive checksum mismatch: {actual_archive}")
    temporary.replace(target)
    print(f"PASS {target} {actual_archive}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / ARCHIVE_NAME,
        help="output ZIP path",
    )
    args = parser.parse_args()
    reconstruct(args.out.resolve())


if __name__ == "__main__":
    main()
