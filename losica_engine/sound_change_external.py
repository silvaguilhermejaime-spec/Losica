from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
from pathlib import Path


def _parse_output_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    out = []
    for line in lines:
        # Accept plain output or common "input -> output" / "input => output" displays.
        if "=>" in line:
            line = line.rsplit("=>", 1)[1].strip()
        elif "->" in line:
            line = line.rsplit("->", 1)[1].strip()
        out.append(line)
    return out


def apply_external_sound_change(
    forms: list[str],
    *,
    rules_path: str | Path,
    command: list[str] | str,
    command_contract: str = "lexurgy",
) -> list[str]:
    """Apply an installed sound-change engine to a batch of forms.

    ``lexurgy`` contract calls ``lexurgy <rules> <words>`` and reads stdout.
    ``generic`` contract substitutes ``{rules}`` and ``{words}`` in command
    tokens and reads stdout. The configured executable supplies the historical
    transformation runtime.
    """
    if not forms:
        return []
    cmd = shlex.split(command) if isinstance(command, str) else list(command)
    with tempfile.TemporaryDirectory(prefix="losica_sound_change_") as td:
        words = Path(td) / "words.txt"
        words.write_text("\n".join(forms) + "\n", encoding="utf-8")
        rules = Path(rules_path)
        if command_contract == "lexurgy":
            run = cmd + [str(rules), str(words)]
        elif command_contract == "generic":
            run = [x.replace("{rules}", str(rules)).replace("{words}", str(words)) for x in cmd]
        else:
            raise ValueError("command_contract must be lexurgy or generic")
        proc = subprocess.run(run, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                "sound-change engine failed\n"
                f"command: {run!r}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        out = _parse_output_lines(proc.stdout)
        if len(out) != len(forms):
            raise RuntimeError(
                f"sound-change engine returned {len(out)} forms for {len(forms)} inputs"
            )
        return out


def load_integration_config(path: str | Path) -> dict:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if obj.get("schema") not in {"losica-integrations/1", "losica-integrations/2"}:
        raise ValueError("losica-integrations/1 or losica-integrations/2 required")
    return obj
