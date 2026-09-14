# Losica Language Generator 0.29.0

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

`records.json` links descriptions to recording positions, never to meanings:

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

See `CAUSAL_ARCHITECTURE.md` for the input schema, ordered computation, and
acceptance gates. The earlier typological generator remains available through
`GENERATE_LEGACY_LANGUAGE.py` and `FINALIZE_LEGACY_LANGUAGE.py`.

## Run without a local computer

- [Phone instructions](RUN_FROM_PHONE.md)
- [Google Colab runner](Losica_Colab.ipynb)
- **Actions → Build Losica → Run workflow** creates a validated downloadable
  language artifact without installing the engine on the phone.
- The same workflow publishes `losica-complete-release`, containing the exact
  0.29 engine, generated language, and external-source catalog.
