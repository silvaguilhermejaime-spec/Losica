from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path

from .config import load_phonology
from .external_retrieval import load_ranking, run_external_backend
from .world_audio import world_acoustic_to_wav

SCHEMA = "losica-word-candidates/3"


def load_transcriptions(path: str | Path) -> dict[str, dict]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if obj.get("schema") != "losica-imitation-transcriptions/1":
        raise ValueError("imitation transcription set required")
    return {
        r["imitation_id"]: r
        for r in obj["records"]
        if r.get("status") == "accepted" and r.get("tokens")
    }


def syllable_patterns(cfg):
    patterns = []
    for onset in cfg.onsets:
        for vowel in cfg.vowels:
            for coda in cfg.codas:
                tokens = tuple(x for x in (onset, vowel, coda) if x)
                text = f"{onset}{vowel}{coda}"
                patterns.append((tokens, text))
    patterns.sort(key=lambda z: (-len(z[0]), z[1]))
    return patterns


def syllabify_tokens(tokens: list[str] | tuple[str, ...], cfg, max_syllables: int = 12):
    tokens = tuple(tokens)
    patterns = syllable_patterns(cfg)
    out = []

    def rec(i, syllables):
        if i == len(tokens):
            out.append(tuple(syllables))
            return
        if len(syllables) >= max_syllables:
            return
        for patt, text in patterns:
            if tokens[i:i + len(patt)] == patt:
                rec(i + len(patt), syllables + [text])

    rec(0, [])
    return sorted(set(out))


def candidates_from_ranking(
    ranking_obj: dict,
    *,
    transcriptions_path: str | Path,
    phonology_path: str | Path,
    top_imitation_count: int = 64,
) -> dict:
    cfg = load_phonology(phonology_path)
    transcripts = load_transcriptions(transcriptions_path)
    ranking = ranking_obj["ranking"][:top_imitation_count]
    grouped = {}
    for row in ranking:
        tr = transcripts.get(row["imitation_id"])
        if not tr:
            continue
        syllabifications = syllabify_tokens(tr["tokens"], cfg)
        for syllables in syllabifications:
            g = grouped.setdefault(syllables, {
                "syllables": list(syllables),
                "evidence": [],
                "score_sum": 0.0,
                "speakers": set(),
            })
            g["score_sum"] += row["score"]
            if row.get("speaker_id"):
                g["speakers"].add(row["speaker_id"])
            g["evidence"].append({
                "imitation_id": row["imitation_id"],
                "speaker_id": row.get("speaker_id", ""),
                "retrieval_score": row["score"],
                "transcription_provenance": tr["provenance"],
            })

    candidates = []
    for syllables, g in grouped.items():
        for prominence in range(len(syllables)):
            candidates.append({
                "preproto_form": ".".join(syllables),
                "prominence": prominence,
                "annotated_form": ".".join(("ˈ" if i == prominence else "") + s for i, s in enumerate(syllables)),
                "evidence_count": len(g["evidence"]),
                "speaker_count": len(g["speakers"]),
                "aggregate_retrieval_score": g["score_sum"],
                "evidence": g["evidence"],
            })
    candidates.sort(key=lambda c: (
        -c["speaker_count"],
        -c["evidence_count"],
        -c["aggregate_retrieval_score"],
        c["preproto_form"],
        c["prominence"],
    ))
    return {
        "schema": SCHEMA,
        "retrieval_backend": ranking_obj.get("backend", {}),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def generate_word_candidates(
    query: str | Path,
    *,
    transcriptions_path: str | Path,
    phonology_path: str | Path,
    ranking_path: str | Path | None = None,
    backend_command: list[str] | str | None = None,
    top_imitation_count: int = 64,
) -> dict:
    query = Path(query)
    with tempfile.TemporaryDirectory(prefix="losica_word_query_") as td:
        if query.suffix.lower() == ".json":
            query_wav = world_acoustic_to_wav(query, Path(td) / "query.wav")
        else:
            query_wav = query

        if ranking_path is not None:
            ranking = load_ranking(ranking_path)
        elif backend_command is not None:
            ranking = run_external_backend(query_wav, command=backend_command, out_path=Path(td) / "ranking.json")
        else:
            raise ValueError("provide --ranking from QBV or --backend-command")

        result = candidates_from_ranking(
            ranking,
            transcriptions_path=transcriptions_path,
            phonology_path=phonology_path,
            top_imitation_count=top_imitation_count,
        )
        result["query_waveform"] = str(query)
        return result


def append_accepted_candidate(candidates_path: str | Path, *, index: int, lexicon_path: str | Path,
                              lexeme_id: str, category_id: str, provenance: str):
    obj = json.loads(Path(candidates_path).read_text(encoding="utf-8"))
    if obj.get("schema") != SCHEMA:
        raise ValueError("word-candidate file required")
    candidate = obj["candidates"][index]
    p = Path(lexicon_path)
    exists = p.exists() and p.stat().st_size > 0
    with p.open("a", encoding="utf-8", newline="") as f:
        fields = ["lexeme_id", "category_id", "preproto_form", "prominence", "provenance"]
        w = csv.DictWriter(f, delimiter="\t", fieldnames=fields, lineterminator="\n")
        if not exists:
            w.writeheader()
        w.writerow({
            "lexeme_id": lexeme_id,
            "category_id": category_id,
            "preproto_form": candidate["preproto_form"],
            "prominence": candidate["prominence"],
            "provenance": provenance,
        })
    return candidate


def main(argv=None):
    ap = argparse.ArgumentParser(description="Create Pre-Proto-Losica forms from human vocal-imitation evidence")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--query", required=True, help="Losica WAV or world acoustic JSON")
    group = g.add_mutually_exclusive_group(required=True)
    group.add_argument("--ranking", help="QBV ranking JSON")
    group.add_argument("--backend-command", help="external QBV bridge command")
    g.add_argument("--transcriptions", required=True)
    g.add_argument("--phonology", default="config/preproto.json")
    g.add_argument("--out", required=True)
    g.add_argument("--top-imitations", type=int, default=64)

    a = sub.add_parser("accept")
    a.add_argument("--candidates", required=True)
    a.add_argument("--candidate-index", type=int, required=True)
    a.add_argument("--lexicon", default="data/lexicon.tsv")
    a.add_argument("--lexeme-id", required=True)
    a.add_argument("--category-id", required=True)
    a.add_argument("--provenance", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "generate":
        obj = generate_word_candidates(
            args.query,
            ranking_path=args.ranking,
            backend_command=args.backend_command,
            transcriptions_path=args.transcriptions,
            phonology_path=args.phonology,
            top_imitation_count=args.top_imitations,
        )
        Path(args.out).write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"candidate_count": len(obj["candidates"]), "out": args.out}, sort_keys=True))
    else:
        c = append_accepted_candidate(
            args.candidates,
            index=args.candidate_index,
            lexicon_path=args.lexicon,
            lexeme_id=args.lexeme_id,
            category_id=args.category_id,
            provenance=args.provenance,
        )
        print(json.dumps({"accepted": c["annotated_form"], "lexicon": args.lexicon}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
