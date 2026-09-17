# Losican historical phonology

## Scope and evidential status

This document connects the canonical Late Pre-Proto-Losica stage to the two
documented modern daughter languages without collapsing distinct historical
levels. It distinguishes three kinds of statement:

1. **implemented reconstruction** — a change performed by
   `config/transition.json`;
2. **documented daughter history** — a change stated in the Komuheft or
   Tegofarela description;
3. **unresolved reconstruction** — a chronology or conditioning that the
   available descriptions do not determine.

The machine-readable companion is `config/family_history.json`. Its
Proto-Losica inventory has status `provisional`: the inventory is exactly the
output segment set licensed by the implemented Pre-Proto transition, but a
larger body of cognate sets is still needed for a full comparative
reconstruction.

## Family chronology

| Stage | Approximate position | Status |
|---|---:|---|
| Late Pre-Proto-Losica | ends c. 800 | canonical input stage |
| Proto-Losica | c. 800–1036 | implemented, provisional reconstruction |
| Komuheftic / Sisengwigwo split | c. 1036 | established project chronology |
| Komuheft | later Komuheftic descendant | modern description supplied |
| Tegofarela | develops from Sisengwigwo by c. 1736 | modern description supplied |

No individual sound change is assigned an absolute date merely from this
table. The daughter descriptions establish relative ordering in several rule
chains, but not a complete dated sequence for either intermediate ancestor.

## Late Pre-Proto-Losica to Proto-Losica

Late Pre-Proto-Losica begins with consonants `/p t k kʼ m n l r/`, vowels
`/i a u/`, the syllable model `(C)V(C)`, and one prominent syllable per root.
The historical engine applies the following operations in order:

1. `p` lenites to `β` in codas and between vowels;
2. postnasal `mp nt nk` become `b d g`;
3. non-prominent high vowels adjacent to a vowel may become `j w`;
4. `tj kw gw` coalesce as `ts kʷ gʷ`;
5. non-prominent syllabic `i u` lower to `e o`.

This gives the provisional Proto-Losica inventory:

| Type | Segments |
|---|---|
| Consonants | `/p t k kʼ b d g kʷ gʷ ts β m n l r j w/` |
| Vowels | `/i e a o u/` |

The inventory records possible outputs of the transition. It does not claim
that every output had equal lexical frequency or unrestricted distribution.
Glide formation branches where the prominence condition permits more than one
analysis; the engine preserves those alternatives instead of silently choosing
one.

## High-value branch correspondences

The strongest present evidence for the family split comes from contrasting
outcomes of the same Proto-Losica segments:

| Proto-Losica | Komuheft | Tegofarela | Diagnostic value |
|---|---|---|---|
| `*kʼ` | `/k/` | `/ʔ/` | direct branch contrast |
| `*ts` | `*s > *h > ∅` | `*s > /h/` | shared early direction, distinct endpoint |
| `*kʷ` | `/hʷ/`, with a special pre-`e` path to `/ʃ/` | `*fʷ > *f > /p/` | strong branch contrast |
| `*gʷ` | `/kʷ/`, sometimes continuing toward `/ww/` | `/ʋ/` or vocalized `/ʉ̟/` | multiple daughter innovations |
| `*β` | `*v > /u/`, optionally nonsyllabic | final deletion with a retained mora | branch-specific treatment |

The two descriptions also share the historical example `*igwara`, but its
later outcomes differ:

```text
Komuheft:    *igwara > *ikwara > *ipwara > *ibwara >
             *iβwara > *ivwara > *iuwara > /iwwara/ [iwːara]

Tegofarela: *igwara > *iʋara > /iʋaːa/
```

The shared input makes this a useful comparison; it does not on its own prove
that every intermediate step belongs immediately after the c. 1036 split.

## Komuheftic evidence from Komuheft

Komuheft preserves a five-vowel system `/i e a o u/` but substantially
reorganizes the Proto consonants. The inherited voiceless stops fricate before
the inherited voiced stops devoice:

| Earlier segment | Komuheft development |
|---|---|
| `*p` | `*ɸ > /f/` |
| `*t` | `/θ/` |
| `*k` | `*x > /h/` outside intervocalic position; `/g/` intervocalically |
| `*b *d *g` | `/p t k/` |
| `*gʷ` | `/kʷ/` |

That relative order prevents the two stop series from merging prematurely.
Other documented developments include `*n > /ɲ/` and `*l > /ʎ/` before `i`
or `j`, partial creation of `/ŋ/` through nasal-velar assimilation, final
`/i/` epenthesis after an illegal coda, and penultimate stress whose placement
is not changed by that epenthesis.

The loss `*ts > *s > *h > ∅` precedes the later creation of `/h/` from `*k`.
Similarly, inherited `*kʷ` becomes `/hʷ/` before inherited `*gʷ` creates a new
`/kʷ/`. These are documented counterfeeding chronologies and therefore belong
in the evidence model.

## Sisengwigwo evidence from Tegofarela

Tegofarela has a moraic prosodic system with phonemic vowel length and
phonological nasalization. Its modern eight-quality vowel inventory is
`/i ɨ ʉ̟ e̞ o̞ ɛ ɔ ɑ̟/`. The available history documents several innovations
that must postdate Proto-Losica, while leaving their placement within the
Sisengwigwo-to-Tegofarela interval open.

Important consonant developments include:

| Earlier segment | Tegofarela development |
|---|---|
| `*kʷ` | `*fʷ > *f > /p/` |
| `*kʼ` | `/ʔ/` |
| `*ts` | `*s > /h/`; modern `/s/` is later reintroduced |
| intervocalic `*g` | `*ɣ̞ > /ɰ/` |
| `*gʷ` | consonantal `/ʋ/` or vocalized `/ʉ̟/` |

Deletion of final `*β`, `*t`, and `*k` leaves a lexical mora and produces
compensatory lengthening. Intervocalic `*r` in affected simple roots behaves
the same way; in morphologically extended forms it survives that deletion
window and later develops as `*r > *ɹ > /j/`. The contrast is historical
allomorphy, not synchronic insertion of `/j/`.

The derivational grouping/concentration affix supplies a separately documented
chain `*ip > *iβ̞ > /ɨ/`. Nasal-coda loss and phonetic prenasalization also feed
parts of the modern lexical nasalization system, but those probabilistic paths
are not yet represented as deterministic Proto correspondence rules.

## Reconstruction boundaries

The current evidence does **not** yet establish:

- complete phoneme inventories for intermediate Komuheftic and Sisengwigwo;
- absolute dates for the individual branch changes;
- the conditioning of the consonantal and vocalized Tegofarela reflexes of
  `*gʷ`;
- a daughter reflex for every Proto segment in every environment;
- enough regular cognate sets to promote the Proto inventory from provisional
  to established.

New historical claims should be added only when they name a source section,
state an environment, distinguish phonemic from phonetic outcomes, and avoid
using a modern inventory as proof of an undocumented retention.
