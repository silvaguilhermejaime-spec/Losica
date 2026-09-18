# Losican comparative lexicon

## Current evidence

The supplied Komuheft and Tegofarela descriptions are primarily phonological,
not lexical. Together they contain four explicit historical lexical-form
derivations, only one of which occurs in both descriptions. The initial
comparative lexicon records all four and treats every missing reflex or meaning
as an evidence gap.

The validated data is in `data/losican_cognates.json`. Forms are stored without
notation delimiters; each stage separately identifies reconstructed, phonemic,
phonetic, or orthographic notation.

| ID | Provisional Proto form | Komuheft outcome | Tegofarela outcome | Coverage | Gloss |
|---|---|---|---|---|---|
| `CG0001` | `*igwara` | `/iwwara/ [iwːara]` | `/iʋaːa/` ⟨ivaaa⟩ | complete | unresolved |
| `CG0002` | `*Kwaratsiβ` | `/warajwi/` | missing evidence | partial | unresolved |
| `CG0003` | `*Atsaokwo` | `/(a)oʃe/` | missing evidence | partial | unresolved |
| `CG0004` | `*igwaramira` | missing evidence | `/iʋajamija/` ⟨ivajamija⟩ | partial | unresolved |

Here, **complete** means that both supplied daughter descriptions contain a
reflex. It does not mean that the etymology, meaning, or every intermediate
stage is fully reconstructed.

## The two-branch comparison

`CG0001` is currently the sole two-branch comparison:

```text
Proto-Losica *igwara

Komuheft:
*igwara > *ikwara > *ipwara > *ibwara > *iβwara >
*ivwara > *iuwara > *iwwara > /iwwara/ [iwːara]

Tegofarela:
*igwara > *iʋara > /iʋaːa/ ⟨ivaaa⟩
```

This form supports the distinct treatment of `*gʷ` and intervocalic `*r` in
the daughter histories. Its gloss is absent from both sources, so it currently
supports phonological comparison but no lexical-semantic conclusion.

## Morphological evidence

The Tegofarela description contrasts the simple `*igwara` form with extended
`*igwaramira`:

```text
simple:   *igwara     > *iʋara     > /iʋaːa/
extended: *igwaramira > *iʋaramira > /iʋajamija/
```

The simple form loses intervocalic `*r` and retains a mora, producing
compensatory lengthening. The extended form preserves `*r` through that
deletion period; it later develops through `*ɹ` to `/j/`. `CG0004` links to
`CG0001` as a related extended form. The data does not assign a morphological
segmentation because the source supplies no explicit morpheme boundary or
meaning.

## Partial records

`*Kwaratsiβ` and `*Atsaokwo` have complete Komuheft derivations but no supplied
Tegofarela reflexes. They remain useful because they exercise several ordered
Komuheft changes, including coda repair, `*β` vocalization, glide formation,
and the special development of final `*kʷo`. Their records use
`missing_evidence` for Sisengwigwo instead of predicting a Tegofarela form.

The optional or uncertain parenthesized material in `/(a)oʃe/` is preserved
exactly as written in the source. The comparative register does not resolve
that alternation.

## Admission standard

A new entry requires:

- an exact source document and section;
- the source's full stated derivation chain;
- notation type for every stage;
- one explicit record for each branch, including `missing_evidence` where
  appropriate;
- a separate semantic status, with a gloss only when the source identifies it;
- `provisional_mapping` when assignment to Proto-Losica is inferred from the
  project chronology rather than explicitly labeled by the source.

The next evidence threshold is a wordlist with glossed Komuheft and Tegofarela
forms. Regular comparisons can then test the proposed Proto inventory and
replace partial records with genuine multi-item cognate sets.
