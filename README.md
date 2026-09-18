# Losica Language Generator 0.32.0

## Build and use the reversible planetary register

Losica 0.32 represents each of the 22 advanced physical quantities as a prefix
expression made from reusable standalone atoms and fixed-arity operators. The
quantity ID remains metadata for exact source recovery.
The register is grounded in the `losica-131757842` physical-climate release.
Its scope is exclusively physical; culture, perception, metaphor, people,
biology, and acoustics remain outside the model.

Every claim has the order `CLAIM EVIDENCE SUBJECT QUANTITY-EXPRESSION NUMBER
UNIT MODEL END`; the expression is variable-length but exactly parseable from
operator arities. `Sampled`, `derived`, `modeled`, `conditioned`, or
`uncertain` must be said first. Exact expression trees, decimal strings, units,
model IDs, and source fields are recoverable by the decoder.

```bash
python BUILD_PLANETARY_REGISTER.py --out planetary-register.json
python USE_PLANETARY_REGISTER.py planetary-register.json expression quantity:semimajor_axis
python USE_PLANETARY_REGISTER.py planetary-register.json say fact:mean_solar_day
python USE_PLANETARY_REGISTER.py planetary-register.json say fact:mean_solar_day --spoken-numbers
python USE_PLANETARY_REGISTER.py planetary-register.json analyze "LOSICA CLAIM"
```

Compact writing uses one decimal token. Claim length varies with the quantity
tree; the optional spoken form expands each numeric character into a Losica
word and preserves every digit. Both satisfy `decode(encode(record)) ==
record`. Every analysis lists each word's IPA, stable semantic ID, operator
arity, syntactic role, semantic burden, and exact source pointer. See
[PLANETARY_REGISTER.md](PLANETARY_REGISTER.md).

## Build the minimal semantic kernel and expand it

Losica can now build a deterministic 69-form semantic kernel: the 65 meanings
in the 2022 condensed Natural Semantic Metalanguage inventory plus four overt
structural forms for patient, recipient/beneficiary, location/time, and
questions. The artifact records NSM with research-proposal status and reserves
universal-minimum status for future evidence.

All semantic meanings use one category-neutral `root` class. Reference,
predicate, entity-modifier, and event-modifier behavior comes from construction
position. Only `relator` and `clause_operator` remain as closed grammatical
classes.

Build only the kernel:

```bash
python BUILD_SEMANTIC_LANGUAGE.py --kernel-only --out semantic-kernel.json
```

Build the kernel and expand it with all 4,033 pinned Concepticon concepts:

```bash
python BUILD_SEMANTIC_LANGUAGE.py --out semantic-language.json
```

Concepticon provides definitions and identifiers for these concepts. Verified
NSM decompositions come from separately cited analyses. Expanded entries carry
the machine labels `lexicalized_source_concept` and
`prime_decomposition: not_asserted`; the second label records the current
evidence state. Cited sources license each prime analysis. English glosses serve
display, while the seed and stable semantic IDs determine forms.

## Build and use the working language

Losica 0.30 added a compact usable layer with 4,033 stable semantic IDs from the
pinned Concepticon 3.4.0 inventory. Every lexical and grammatical form is
generated from seed `19020`; English glosses are used only by the input/display
adapter. Losica form assignment reads the seed and numeric semantic IDs.

```bash
python BUILD_WORKING_LANGUAGE.py --out working-language.json
python USE_WORKING_LANGUAGE.py translate working-language.json "Can you buy bread for me today?"
python USE_WORKING_LANGUAGE.py translate working-language.json "It's always been like this"
python USE_WORKING_LANGUAGE.py lookup working-language.json always
python USE_WORKING_LANGUAGE.py analyze working-language.json "LOSICA OUTPUT"
```

The translator emits the source-backed semantic graph, Losica sentence,
phonemic forms, interlinear token meanings, and exact Concepticon IDs. Unknown
source words produce an explicit lookup error. The compact grammar
currently handles ordinary single-clause statements and questions, pronouns,
patients, recipients/beneficiaries, properties, common time modifiers,
past/prospective/perfective, negation, potential mood, and proximal/distal reference.
Its supported domain is controlled semantic translation for these constructions.

## Late Pre-Proto-Losica grammar

The canonical historical stage is Late Pre-Proto-Losica, an undated first
Losican language ending around c. 800. It is predominantly isolating, uses SOV
clauses and postpositions, and builds compounds in modifier-head order. Free
particles express roles, aspect, mood, polarity, deixis, and questions.

Unmarked predicates are tenseless. The particle `tam` retains its established
surface form and marks the prospective: an approaching, intended, planned, or
expected event. Time expressions and discourse locate events independently.

The reference grammar also records the maritime homeland, three-solar-turn
wake-sleep cycle, mobile clans, spatial system, and the boundary between the
canonical grammar and the legacy agglutinative generator. See
[PRE_PROTO_LOSICA_GRAMMAR.md](docs/PRE_PROTO_LOSICA_GRAMMAR.md).
Its executable nominal layer now includes unmarked possessor-head phrases,
anchor-relation kin terms, and four culturally grounded clan-kin compounds.

The historical bridge into Proto-Losica and the separately evidenced
Komuheftic and Sisengwigwo developments are documented in
[LOSICAN_HISTORICAL_PHONOLOGY.md](docs/LOSICAN_HISTORICAL_PHONOLOGY.md). The
correspondence claims also have a validated machine-readable register at
`config/family_history.json`; uncertain intermediate reconstructions remain
explicitly marked, and modern inventories serve as evidence requiring separate
correspondence support.

The [historical worked-example register](docs/HISTORICAL_WORKED_EXAMPLES.md)
indexes the derivation examples printed in the supplied Komuheft and
Tegofarela descriptions. It records source coverage and notation, classifies
the material as phonological worked examples, and leaves source-unspecified
meanings unassigned.

[Intermediate reconstruction constraints](docs/INTERMEDIATE_RECONSTRUCTION_CONSTRAINTS.md)
identify which Proto segments are directly required by each branch's rules and
attested forms. They preserve the distinction between diachronic evidence and
a complete synchronic Komuheftic or Sisengwigwo inventory.

On GitHub, **Actions → Build working Losica → Run workflow** builds and tests the
same `losica-working-language` artifact for phone download.

## Causal observation engine

Losica's default engine generates a language from unnamed numeric transducer
streams, opaque controls, time, and recurrence. It learns multi-step events,
lexical regions, partitions, productive markers, ordered constructions, and
stored historical roots by testing whether messages improve reconstruction of
held-out later samples.

The generated language owns `ev:*`, `sr:*`, `sp:*`, `sc:*`, `md:*`, `mc:*`,
`cx:*`, and `lx:*` identities. Human-language expressions live in separate
post-generation adapter files keyed to those internal identities.

Create a finished language:

```bash
python FINALIZE_LANGUAGE.py --seed 19020 --vocabulary-scale large --out language.json
```

Validate it:

```bash
python VALIDATE_COMPLETE_LANGUAGE.py language.json
```

Inspect and analyze its own utterances:

```bash
python USE_LANGUAGE.py language.json event ev:000001
python USE_LANGUAGE.py language.json analyze "GENERATED UTTERANCE"
```

Build a human-language interface after generation:

```bash
python ALIGN_LANGUAGE.py language.json build records.json --namespace en --out en.adapter.json
python ALIGN_LANGUAGE.py language.json external-to-losica en.adapter.json "external sentence"
```

`records.json` links descriptions exclusively to recording positions:

```json
[
  {
    "external_id": "recording-description:1",
    "expression": "a description recorded during the experience",
    "source_offset_ranges": [[1200, 1280]]
  }
]
```

The adapter derives overlapping `ev:*` records and their `sr:*` regions. Repeated
descriptions train reusable one-to-four-word links. Translation requires either
an exact aligned record or at least 80% learned token coverage.

`--stream PATH` accepts a strict `losica-causal-stream/1` file. Omitting the
option selects a deterministic numeric fixture for installation tests.

Generate from real audio or video, while keeping external wording outside the
causal generator:

```bash
python GENERATE_REAL_LANGUAGE.py media/manifest.json --out-dir dist/real-media
```

`losica_engine.media_stream` extracts fixed label-free acoustic and visual
measurements. An optional external catalog joins afterward by recording ID and
time range. The causal stream stays byte-identical across annotation changes.
For broader surface-form coverage, install `.[nlp]`, download the required Stanza
model once on the build machine, and add `--external-parser stanza`. Only the
observed analysis and an ambiguity-filtered surface-to-lemma table enter the
adapter. Phone translation uses the resulting adapter artifact.

`external_sources/build_catalog.py --include-egocom` adds 24,334 utterances
reconstructed exactly from EgoCom's timestamped human word stream. After the
official 240p media download, `external_sources/build_egocom_manifest.py` selects
one stable first-person view per segment for the real-media command above.

See `CAUSAL_ARCHITECTURE.md` for the input schema, ordered computation, and
acceptance gates. The earlier typological generator remains available through
`GENERATE_LEGACY_LANGUAGE.py` and `FINALIZE_LEGACY_LANGUAGE.py`.

## Run from a phone

- [Phone instructions](RUN_FROM_PHONE.md)
- [Google Colab runner](Losica_Colab.ipynb)
- **Actions → Build Losica → Run workflow** creates a validated downloadable
  language artifact; the phone only needs a browser.
- The same workflow publishes `losica-complete-release`, containing the exact
  0.29 engine, generated language, and external-source catalog.
- **Actions → Build Real-Media Losica → Run workflow** downloads pinned real
  ESC-10 audio and an OpenCV sample video, generates a language from their raw
  signals, and publishes bidirectional alignment results as
  `losica-real-media-demo`.
- **Actions → Build working Losica → Run workflow** publishes the compact 4,033-
  concept dictionary and translator state used by `USE_WORKING_LANGUAGE.py`.
