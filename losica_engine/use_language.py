"""Command-line access to a generated Losica language snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .grammar_v021 import LanguageExecutor
from .surface_analysis import analyze_surface
from .translation import translate


def load_state(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_graph(value: str) -> dict:
    path = Path(value)
    text = path.read_text(encoding="utf-8") if path.is_file() else value
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("semantic message requires one JSON object")
    return obj


def _load_graphs(value: str) -> list[dict]:
    path = Path(value)
    text = path.read_text(encoding="utf-8") if path.is_file() else value
    obj = json.loads(text)
    if not isinstance(obj, list) or any(not isinstance(x, dict) for x in obj):
        raise ValueError("text realization requires a JSON array of semantic-message objects")
    return obj


def _executor(state: dict) -> LanguageExecutor:
    return LanguageExecutor(
        lexicon=state["lexicon"], paradigms=state["paradigms"],
        morphology=state["morphology"], profile=state["profile"],
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description="Realize and analyze a generated Losica language snapshot")
    ap.add_argument("state", help="generated language.json")
    sub = ap.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="analyze a written Losica expression")
    a.add_argument("text")
    r = sub.add_parser("realize", help="realize a typed semantic JSON graph")
    r.add_argument("graph", help="JSON text or a path to a JSON file")
    t = sub.add_parser("translate", help="use the bundled controlled English adapter")
    t.add_argument("text")
    l = sub.add_parser("lookup", help="look up a generated lexeme by form, ID, or display label")
    l.add_argument("term")
    n = sub.add_parser("numeral", help="realize a cardinal numeral in the generated numeral system")
    n.add_argument("value", type=int)
    tx = sub.add_parser("text", help="realize a JSON array of semantic messages as a text")
    tx.add_argument("graphs", help="JSON text or a path to a JSON file")
    args = ap.parse_args(argv)

    state = load_state(args.state)
    if args.command == "analyze":
        result = analyze_surface(state, args.text)
    elif args.command == "realize":
        result = _executor(state).realize(_load_graph(args.graph))
    elif args.command == "translate":
        result = translate(state, args.text)
    elif args.command == "lookup":
        term = args.term.casefold()
        rows = []
        for lex in state["lexicon"]:
            display = lex.get("display", {})
            keys = {
                lex["lexeme_id"].casefold(), lex.get("concept", "").casefold(),
                lex.get("orthographic", "").casefold(), lex.get("form", "").replace(".", "").casefold(),
                str(display.get("en", "")).casefold(),
            } | {str(x).casefold() for x in display.get("en_aliases", [])}
            if term in keys:
                rows.append(lex)
        result = {"query": args.term, "matches": rows}
    elif args.command == "numeral":
        executor = _executor(state)
        tokens = executor._numeral_tokens(args.value)
        result = {
            "value": args.value,
            "system": state["profile"]["numeral_system"],
            "phonemic": " ".join(x["phonemic"] for x in tokens),
            "orthographic": " ".join(x["orthographic"] for x in tokens),
            "tokens": tokens,
        }
    else:
        executor = _executor(state)
        realized = [executor.realize(graph) for graph in _load_graphs(args.graphs)]
        result = {"sentences": realized, "text": " ".join(x["orthographic_sentence"] for x in realized)}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
