from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf


def world_acoustic_to_wav(source: str | Path, out: str | Path) -> Path:
    obj = json.loads(Path(source).read_text(encoding="utf-8"))
    if obj.get("schema") == "losica-acoustic-path/3":
        sound = obj["propagated_waveform"]
    elif obj.get("schema") == "propagated-sound/2":
        sound = obj
    else:
        raise ValueError("world acoustic input requires losica-acoustic-path/3 or propagated-sound/2")
    fs = int(sound["sample_rate_hz"])
    x = np.asarray(sound["pressure_Pa"], dtype=np.float64)
    if fs < 1 or x.ndim != 1 or x.size < 2 or not np.isfinite(x).all():
        raise ValueError("finite pressure waveform and positive sample rate required")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, x.astype(np.float32), fs, subtype="FLOAT")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    print(world_acoustic_to_wav(args.input, args.out))


if __name__ == "__main__":
    main()
