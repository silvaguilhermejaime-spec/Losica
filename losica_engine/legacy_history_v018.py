
from dataclasses import dataclass
from itertools import product
from .phonology import Root, tokenize_surface
from .config import PhonologyConfig, TransitionConfig

@dataclass(frozen=True)
class Token:
    value: str
    kind: str
    syllable: int
    prominent: bool = False

@dataclass(frozen=True)
class Stage:
    label: str
    form: str

@dataclass(frozen=True)
class Derivation:
    stages: tuple[Stage, ...]

    @property
    def proto(self) -> str:
        return self.stages[-1].form

def parse_syllable(syl: str, index: int, prominent: bool, cfg: PhonologyConfig) -> list[Token]:
    segs = tokenize_surface(syl, cfg.consonants, cfg.vowels)
    vpos = [i for i, s in enumerate(segs) if s in cfg.vowels]
    if len(vpos) != 1:
        raise ValueError(f"syllable {syl!r} requires exactly one nucleus")
    vi = vpos[0]
    return [
        Token(seg, "V" if i == vi else "C", index, prominent if i == vi else False)
        for i, seg in enumerate(segs)
    ]

def root_tokens(root: Root, cfg: PhonologyConfig) -> list[Token]:
    out = []
    for i, syl in enumerate(root.syllables):
        out.extend(parse_syllable(syl, i, i == root.prominence, cfg))
    return out

def render(tokens: list[Token]) -> str:
    return "".join(t.value for t in tokens)

def replace_sequence(tokens, i, count, token):
    return tokens[:i] + [token] + tokens[i+count:]

def p_to_beta(tokens: list[Token], cfg: PhonologyConfig, tr: TransitionConfig) -> list[Token]:
    out = tokens[:]
    for i, t in enumerate(tokens):
        if t.kind != "C" or t.value != tr.p_segment:
            continue

        if "coda" in tr.p_environments:
            same_syllable_vowel_before = any(
                x.kind == "V" and x.syllable == t.syllable
                for x in tokens[:i]
            )
            if same_syllable_vowel_before:
                out[i] = Token(tr.p_result, "C", t.syllable)
                continue

        if "intervocalic" in tr.p_environments:
            prev_v = i > 0 and tokens[i-1].kind == "V"
            next_v = i + 1 < len(tokens) and tokens[i+1].kind == "V"
            if prev_v and next_v:
                out[i] = Token(tr.p_result, "C", t.syllable)
    return out

def postnasal_changes(tokens: list[Token], tr: TransitionConfig) -> list[Token]:
    out = tokens[:]
    i = 0
    while i < len(out) - 1:
        a, b = out[i], out[i + 1]
        result = tr.postnasal.get(a.value + b.value)
        if a.kind == b.kind == "C" and result:
            out = replace_sequence(out, i, 2, Token(result, "C", b.syllable))
        else:
            i += 1
    return out

def vowel_runs(tokens: list[Token]) -> list[tuple[int, ...]]:
    runs = []
    current = []
    for i, t in enumerate(tokens):
        if t.kind == "V":
            current.append(i)
        else:
            if len(current) >= 2:
                runs.append(tuple(current))
            current = []
    if len(current) >= 2:
        runs.append(tuple(current))
    return runs



def glide_eligible_indices(tokens: list[Token], tr: TransitionConfig) -> tuple[int, ...]:
    if not tr.glides_enabled:
        return ()

    if tr.glide_condition != "nonprominent_adjacent_vowel":
        raise ValueError(f"glide condition must be one of the registered conditions: {tr.glide_condition!r}")

    eligible = []
    for run in vowel_runs(tokens):
        for i in run:
            t = tokens[i]
            if t.value in tr.glides and not t.prominent:
                eligible.append(i)

    return tuple(eligible)

def glide_branch_count(tokens: list[Token], tr: TransitionConfig) -> int:
    eligible = set(glide_eligible_indices(tokens, tr))
    if not eligible:
        return 1

    total = 1

    for run in vowel_runs(tokens):
        run_eligible = [i for i in run if i in eligible]
        e = len(run_eligible)
        if e == 0:
            continue

        all_vowels_eligible = e == len(run)
        total *= (2 ** e) - (1 if all_vowels_eligible else 0)

    return total

def _iter_run_glide_choices(
    run: tuple[int, ...],
    eligible: set[int],
):
    run_eligible = tuple(i for i in run if i in eligible)

    if not run_eligible:
        yield ()
        return

    all_vowels_eligible = len(run_eligible) == len(run)

    for flags in product((False, True), repeat=len(run_eligible)):
        if all_vowels_eligible and all(flags):
            continue

        yield tuple(
            index
            for index, apply in zip(run_eligible, flags)
            if apply
        )

def iter_glide_options(tokens: list[Token], tr: TransitionConfig):
    eligible = set(glide_eligible_indices(tokens, tr))
    if not eligible:
        yield tokens
        return

    active_runs = tuple(
        run
        for run in vowel_runs(tokens)
        if any(i in eligible for i in run)
    )

    def walk(run_index: int, current: list[Token]):
        if run_index == len(active_runs):
            yield current
            return

        run = active_runs[run_index]

        for glide_indices in _iter_run_glide_choices(run, eligible):
            out = current[:]

            for idx in glide_indices:
                t = out[idx]
                out[idx] = Token(
                    tr.glides[t.value],
                    "G",
                    t.syllable,
                )

            yield from walk(run_index + 1, out)

    yield from walk(0, tokens[:])

def coalescence(tokens: list[Token], tr: TransitionConfig) -> list[Token]:
    out = tokens[:]
    i = 0
    while i < len(out) - 1:
        a, b = out[i], out[i + 1]
        result = tr.coalescence.get(a.value + b.value)
        if a.kind == "C" and b.kind == "G" and result:
            out = replace_sequence(out, i, 2, Token(result, "C", a.syllable))
        else:
            i += 1
    return out

def lower_vowels(tokens: list[Token], tr: TransitionConfig) -> list[Token]:
    if not tr.vowel_lowering_enabled:
        return tokens[:]

    if tr.vowel_lowering_condition != "nonprominent_syllabic":
        raise ValueError(
            f"vowel-lowering condition must be registered: {tr.vowel_lowering_condition!r}"
        )

    out = []
    for t in tokens:
        if t.kind == "V" and not t.prominent and t.value in tr.vowel_lowering:
            out.append(Token(tr.vowel_lowering[t.value], "V", t.syllable, False))
        else:
            out.append(t)
    return out

def prepared_tokens(root: Root, cfg: PhonologyConfig, tr: TransitionConfig) -> tuple[list[Token], list[Token], list[Token]]:
    initial = root_tokens(root, cfg)
    beta = p_to_beta(initial, cfg, tr)
    postnasal = postnasal_changes(beta, tr)
    return initial, beta, postnasal

def historical_branch_count(root: Root, cfg: PhonologyConfig, tr: TransitionConfig) -> int:
    _, _, postnasal = prepared_tokens(root, cfg, tr)
    return glide_branch_count(postnasal, tr)

def iter_derivations(root: Root, cfg: PhonologyConfig, tr: TransitionConfig):
    initial, beta, postnasal = prepared_tokens(root, cfg, tr)
    seen_traces = set()

    for glided in iter_glide_options(postnasal, tr):
        coal = coalescence(glided, tr)
        low = lower_vowels(coal, tr)
        stages = (
            Stage("preproto", root.annotated_form),
            Stage("p_to_beta", render(beta)),
            Stage("postnasal", render(postnasal)),
            Stage("glide", render(glided)),
            Stage("coalescence", render(coal)),
            Stage("vowel_lowering", render(low)),
            Stage("proto", render(low)),
        )
        key = tuple((s.label, s.form) for s in stages)
        if key in seen_traces:
            continue
        seen_traces.add(key)
        yield Derivation(stages)

def proto_forms(root: Root, cfg: PhonologyConfig, tr: TransitionConfig) -> tuple[str, ...]:
    seen = set()
    out = []
    for d in iter_derivations(root, cfg, tr):
        if d.proto not in seen:
            seen.add(d.proto)
            out.append(d.proto)
    return tuple(out)
