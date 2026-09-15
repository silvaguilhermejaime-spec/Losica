# Losica Language Generator 0.30.0

## Build the minimal semantic kernel and expand it

Losica can now build a deterministic 69-form semantic kernel: the 65 meanings
in the 2022 condensed Natural Semantic Metalanguage inventory plus four overt
structural forms for patient, recipient/beneficiary, location/time, and
questions.  NSM is recorded in the artifact as a research proposal rather than
as a proved universal minimum.

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

Concepticon provides definitions and identifiers rather than verified NSM
decompositions for these concepts. The expanded entries are therefore labelled
`lexicalized_source_concept` with `prime_decomposition: not_asserted`. Losica
creates a prime analysis only when backed by a cited source; English glosses
remain display-only. Forms depend only on the seed and stable semantic IDs.

## Build and use the working language

Losica 0.30 adds a compact usable layer with 4,033 stable semantic IDs from the
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
source words fail instead of receiving invented meanings. The compact grammar
currently handles ordinary single-clause statements and questions, pronouns,
patients, recipients/beneficiaries, properties, common time modifiers,
past/future/perfective, negation, potential mood, and proximal/distal reference.
It is a controlled semantic translator, not a claim of unrestricted natural-
language understanding.

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

`--stream PATH` accepts a strict `losica-causal-stream/1` file. With no stream,
the command uses a deterministic numeric fixture for installation tests.

Generate from real audio or video, while keeping external wording outside the
causal generator:

```bash
python GENERATE_REAL_LANGUAGE.py media/manifest.json --out-dir dist/real-media
```

`losica_engine.media_stream` extracts fixed label-free acoustic and visual
measurements. An optional external catalog is joined afterward by recording ID
and time range. Changing every annotation leaves the causal stream byte-identical.
For broader surface-form coverage, install `.[nlp]`, download the required Stanza
model once on the build machine, and add `--external-parser stanza`. Only the
observed analysis and an ambiguity-filtered surface-to-lemma table enter the
adapter; neither Stanza nor its model is required when translating on a phone.

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
