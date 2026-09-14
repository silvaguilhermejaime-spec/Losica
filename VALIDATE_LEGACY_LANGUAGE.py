#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from losica_engine.validation_v021 import validate_complete_language

parser = argparse.ArgumentParser()
parser.add_argument("language")
args = parser.parse_args()
print(json.dumps(validate_complete_language(json.loads(Path(args.language).read_text(encoding="utf-8"))), sort_keys=True))
