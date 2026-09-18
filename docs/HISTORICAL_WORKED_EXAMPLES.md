# Losican historical worked-example register

## Current evidence

The supplied Komuheft and Tegofarela descriptions are phonological. Together
they print four historical derivation examples, one of which uses the same
input in both descriptions. The register copies those examples without
promoting them to lexemes, cognate sets, or a daughter-language vocabulary.

The validated data is in `data/historical_worked_examples.json`. Forms are stored without
notation delimiters; each stage separately identifies reconstructed, phonemic,
phonetic, or orthographic notation.

| ID | Provisional historical input | Komuheft outcome | Tegofarela outcome | Source coverage | Meaning |
|---|---|---|---|---|---|
| `HX0001` | `*igwara` | `/iwwara/ [iwːara]` | `/iʋaːa/` ⟨ivaaa⟩ | both descriptions | not supplied |
| `HX0002` | `*Kwaratsiβ` | `/warajwi/` | not printed | Komuheft only | not supplied |
| `HX0003` | `*Atsaokwo` | `/(a)oʃe/` | not printed | Komuheft only | not supplied |
| `HX0004` | `*igwaramira` | not printed | `/iʋajamija/` ⟨ivajamija⟩ | Tegofarela only | not supplied |

Source coverage reports only where an example is printed. It makes no claim
about cognacy, lexical membership, or an unprinted outcome in the other
language.

## Shared printed input

`HX0001` records the only input printed in both descriptions:

```text
Proto-Losica *igwara

Komuheft:
*igwara > *ikwara > *ipwara > *ibwara > *iβwara >
*ivwara > *iuwara > *iwwara > /iwwara/ [iwːara]

Tegofarela:
*igwara > *iʋara > /iʋaːa/ ⟨ivaaa⟩
```

These two worked chains illustrate distinct treatments of `*gʷ` and
intervocalic `*r`. The shared spelling of the input does not independently
establish a cognate relationship, meaning, or lexical status.

## Morphological evidence

The Tegofarela description contrasts the simple `*igwara` form with extended
`*igwaramira`:

```text
simple:   *igwara     > *iʋara     > /iʋaːa/
extended: *igwaramira > *iʋaramira > /iʋajamija/
```

The simple form loses intervocalic `*r` and retains a mora, producing
compensatory lengthening. The extended form preserves `*r` through that
deletion period; it later develops through `*ɹ` to `/j/`. `HX0004` links to
`HX0001` as a related extended form. The data does not assign a morphological
segmentation because the source supplies no explicit morpheme boundary or
meaning.

## Examples printed in one description

`*Kwaratsiβ` and `*Atsaokwo` have Komuheft derivations and no Tegofarela chain
is printed. They remain useful because they exercise several ordered
Komuheft changes, including coda repair, `*β` vocalization, glide formation,
and the special development of final `*kʷo`. Their records use
`not_printed` for Sisengwigwo instead of predicting a Tegofarela form.

The optional or uncertain parenthesized material in `/(a)oʃe/` is preserved
exactly as written in the source. The worked-example register does not resolve
that alternation.

## Admission standard

A new entry requires:

- an exact source document and section;
- the source's full stated derivation chain;
- notation type for every stage;
- one explicit record for each branch, including `not_printed` where
  appropriate;
- a separate meaning status, with a meaning only when the source identifies it;
- `provisional_mapping` when assignment to Proto-Losica is inferred from the
  project chronology rather than explicitly labeled by the source.

No daughter-language wordlist is part of the project. These records therefore
remain phonological worked examples; future vocabulary is to be constructed as
part of Losica rather than inferred from an absent comparative dataset.
