
from dataclasses import dataclass
from itertools import product
from typing import Iterable, Sequence
from .config import PhonologyConfig

@dataclass(frozen=True)
class Root:
    syllables: tuple[str, ...]
    prominence: int

    @property
    def form(self) -> str:
        return ".".join(self.syllables)

    @property
    def annotated_form(self) -> str:
        return ".".join(
            ("ˈ" if i == self.prominence else "") + s
            for i, s in enumerate(self.syllables)
        )

    @property
    def syllable_count(self) -> int:
        return len(self.syllables)

def tokenize_surface(text: str, consonants: tuple[str, ...], vowels: tuple[str, ...]) -> tuple[str, ...]:
    inventory = sorted(set(consonants) | set(vowels), key=lambda x: (-len(x), x))
    out = []
    i = 0
    while i < len(text):
        for seg in inventory:
            if text.startswith(seg, i):
                out.append(seg)
                i += len(seg)
                break
        else:
            raise ValueError(f"tokenization stopped at offset {i} in {text!r}")
    return tuple(out)

def degeminate_consonants(segments: Sequence[str], consonants: Sequence[str]) -> tuple[str, ...]:
    """Collapse adjacent identical consonants to one surface segment."""
    consonant_set = set(consonants)
    out = []
    for segment in segments:
        if out and segment == out[-1] and segment in consonant_set:
            continue
        out.append(segment)
    return tuple(out)

def legal_syllables(cfg: PhonologyConfig) -> tuple[str, ...]:
    return tuple(
        f"{o}{v}{c}"
        for o, v, c in product(cfg.onsets, cfg.vowels, cfg.codas)
    )

def estimate_root_count(cfg: PhonologyConfig, syllable_counts: Sequence[int], cap: int | None = None) -> int:
    """Count lexical representations; `cap + 1` marks a result above `cap`."""
    total = 0
    for n in sorted(set(syllable_counts)):
        if n < 1:
            raise ValueError("syllable count must be >= 1")
        if cap is not None and n > cap:
            return cap + 1
        # Track the previous coda because a matching following onset would
        # degeminate and duplicate a representation already in the pool.
        by_coda = {
            coda: len(cfg.onsets) * len(cfg.vowels)
            for coda in cfg.codas
        }
        for _ in range(1, n):
            next_by_coda = {coda: 0 for coda in cfg.codas}
            for previous_coda, count in by_coda.items():
                onset_count = len(cfg.onsets) - int(
                    bool(previous_coda) and previous_coda in cfg.onsets
                )
                extension_count = count * onset_count * len(cfg.vowels)
                for coda in cfg.codas:
                    next_by_coda[coda] += extension_count
                    if cap is not None:
                        next_by_coda[coda] = min(next_by_coda[coda], cap + 1)
            by_coda = next_by_coda
        representation_count = sum(by_coda.values())
        total += n * representation_count
        if cap is not None and total > cap:
            return cap + 1
    return total

def generate_roots(cfg: PhonologyConfig, syllable_counts: Sequence[int]) -> Iterable[Root]:
    syllables = legal_syllables(cfg)
    margins = {}
    consonants = set(cfg.consonants)
    for syllable in syllables:
        segments = tokenize_surface(syllable, cfg.consonants, cfg.vowels)
        margins[syllable] = (
            segments[0] if segments[0] in consonants else "",
            segments[-1] if segments[-1] in consonants else "",
        )
    for n in sorted(set(syllable_counts)):
        if n < 1:
            raise ValueError("syllable count must be >= 1")
        for seq in product(syllables, repeat=n):
            if any(
                margins[left][1] and margins[left][1] == margins[right][0]
                for left, right in zip(seq, seq[1:])
            ):
                continue
            for prominence in range(n):
                yield Root(tuple(seq), prominence)

def root_segments(root: Root, cfg: PhonologyConfig) -> tuple[str, ...]:
    out = []
    for syl in root.syllables:
        out.extend(tokenize_surface(syl, cfg.consonants, cfg.vowels))
    return tuple(out)

def contains_any(root: Root, cfg: PhonologyConfig, segments: set[str]) -> bool:
    return bool(set(root_segments(root, cfg)) & segments)

def syllabify_surface(text: str, cfg: PhonologyConfig) -> tuple[str, ...]:
    """Return one legal syllabification of an undelimited surface form.

    Legality is defined entirely by the configured onset/vowel/coda inventories.
    When more than one parse exists, prefer parses that place an available
    consonant in the onset of a following syllable (maximal-onset tie break),
    then prefer fewer codas. This tie break produces deterministic syllable
    serialization among legal parses.
    """
    surface = text.replace(".", "")
    if not surface:
        raise ValueError("surface form must contain at least one segment")
    segments = tokenize_surface(surface, cfg.consonants, cfg.vowels)
    if degeminate_consonants(segments, cfg.consonants) != segments:
        raise ValueError(f"surface form {surface!r} contains an unsimplified double consonant")
    patterns = []
    for onset in cfg.onsets:
        for vowel in cfg.vowels:
            for coda in cfg.codas:
                seq = tuple(x for x in (onset, vowel, coda) if x)
                patterns.append((seq, onset, coda, onset + vowel + coda))

    memo: dict[int, tuple[tuple[tuple[str, str, str], ...], tuple[int, int, int, tuple[str, ...]]] | None] = {}

    def best(i: int):
        if i == len(segments):
            return (), (0, 0, 0, ())
        if i in memo:
            return memo[i]
        candidates = []
        for seq, onset, coda, syl in patterns:
            n = len(seq)
            if tuple(segments[i:i+n]) != seq:
                continue
            rest = best(i+n)
            if rest is None:
                continue
            parsed, score = rest
            onset_bonus = 1 if i > 0 and onset else 0
            coda_penalty = 1 if coda else 0
            # Maximize noninitial onsets, then minimize codas and syllable count.
            new_score = (
                score[0] + onset_bonus,
                score[1] - coda_penalty,
                score[2] - 1,
                (syl,) + score[3],
            )
            candidates.append((((onset, coda, syl),) + parsed, new_score))
        if not candidates:
            memo[i] = None
            return None
        result = max(candidates, key=lambda x: x[1])
        memo[i] = result
        return result

    result = best(0)
    if result is None:
        raise ValueError(f"surface form {surface!r} violates syllable pattern {cfg.syllable}")
    parsed, _ = result
    return tuple(x[2] for x in parsed)


def is_legal_surface(text: str, cfg: PhonologyConfig) -> bool:
    try:
        syllabify_surface(text, cfg)
    except ValueError:
        return False
    return True
