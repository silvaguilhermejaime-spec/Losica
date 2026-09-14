from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

RANKING_SCHEMA = "losica-vocal-retrieval-ranking/1"


def load_ranking(path: str | Path) -> dict:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if obj.get("schema") != RANKING_SCHEMA:
        raise ValueError(f"ranking schema must be {RANKING_SCHEMA}")
    rows = obj.get("ranking")
    if not isinstance(rows, list):
        raise ValueError("ranking must be a list")
    out = []
    seen = set()
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"ranking row {i} must be an object")
        imitation_id = row.get("imitation_id")
        speaker_id = row.get("speaker_id", "")
        score = row.get("score")
        if not isinstance(imitation_id, str) or not imitation_id:
            raise ValueError(f"ranking row {i}: imitation_id required")
        if imitation_id in seen:
            raise ValueError(f"duplicate imitation_id {imitation_id!r}")
        seen.add(imitation_id)
        if not isinstance(score, (int, float)):
            raise ValueError(f"ranking row {i}: numeric score required")
        out.append({
            "imitation_id": imitation_id,
            "speaker_id": str(speaker_id),
            "score": float(score),
            "referent_id": row.get("referent_id"),
        })
    out.sort(key=lambda r: (-r["score"], r["imitation_id"]))
    obj["ranking"] = out
    return obj


def run_external_backend(
    query_wav: str | Path,
    *,
    command: list[str] | str,
    out_path: str | Path,
    extra_args: list[str] | None = None,
) -> dict:
    """Run an external retrieval backend.

    Contract: the command receives ``--query-wav`` and ``--out`` and writes
    losica-vocal-retrieval-ranking/1 JSON. This keeps QBV upstream code and
    checkpoints outside this package while letting Losica consume its output.
    """
    parts = shlex.split(command) if isinstance(command, str) else list(command)
    parts += ["--query-wav", str(query_wav), "--out", str(out_path)]
    if extra_args:
        parts.extend(extra_args)
    proc = subprocess.run(parts, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "external retrieval backend failed\n"
            f"command: {parts!r}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return load_ranking(out_path)


def write_ranking(rows: list[dict], path: str | Path, *, backend: dict | None = None) -> Path:
    payload = {
        "schema": RANKING_SCHEMA,
        "backend": backend or {},
        "ranking": rows,
    }
    p = Path(path)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p
