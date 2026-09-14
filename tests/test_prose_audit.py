import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURFACES = [
    ROOT / "README.md",
    ROOT / "METHODOLOGY.md",
    ROOT / "CHANGELOG.md",
    ROOT / "schemas" / "README.md",
]
NEGATION_NUCLEUS = re.compile(r"\b(?:must\s+not|does\s+not|do\s+not|did\s+not|cannot|can't|never|without|forbidden|prohibited|unsupported|unmapped)\b", re.I)


def test_authored_release_prose_defines_positive_semantics():
    hits = []
    for path in SURFACES:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if NEGATION_NUCLEUS.search(line):
                hits.append((str(path.relative_to(ROOT)), number, line.strip()))
    assert hits == []
