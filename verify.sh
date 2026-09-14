#!/bin/sh
set -eu

python -m pytest -q tests/test_causal_engine.py
python FINALIZE_LANGUAGE.py --seed 19020 --vocabulary-scale large --out /tmp/losica-language.json
python VALIDATE_COMPLETE_LANGUAGE.py /tmp/losica-language.json
