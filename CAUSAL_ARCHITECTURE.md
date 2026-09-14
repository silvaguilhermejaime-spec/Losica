# Losica causal engine

## Generation input

`losica-causal-stream/1` contains:

- `frames[].t`
- `frames[].samples`
- `frames[].controls`
- `frames[].source_offset`
- `source_sha256`

The projector rejects names, labels, goals, rewards, success values, termination
meanings, supplied boundaries, target identities, oracle state, semantic masks,
and pretrained checkpoints. Sensor choice remains an external collection choice;
the generation manifest therefore requires the source operator to exclude a
transducer engineered or calibrated to report a chosen semantic target.

An external stream is accepted only with `losica-collection-attestation/1`.
The gate accepts general optical, acoustic, mechanical, electrical, or mixed
transducers. A molecular-target or other chosen-target sensor fails before its
numbers reach generation. The attestation itself is not a generation material.

## Ordered computation

1. `causal_stream.validate_causal_stream` normalizes numeric streams and fails on
   every unregistered field.
2. `experiential_language.learn_events` creates overlapping multi-step records
   and future-sample targets from time indexes.
3. `derive_regions` proposes seeded numeric projections and keeps a range only
   when its prototype lowers squared reconstruction error on held-out future
   samples.
4. Each accepted range receives `sr:*`; each generated root receives `lx:*`.
5. `derive_constructions` keeps recurring ordered region pairs only when their
   joint prototype beats the mean constituent prototype on held-out events.
6. `causal_grammar.derive_morphology` retains region cells recurring with at
   least 6 distinct hosts across at least 12 events and assigns generated bound
   forms.
7. `causal_history.lexicalize_constructions` fuses supported constructions,
   stores the result as a current one-part root, and preserves the two-part
   source analysis in a replayable historical transition.
8. `causal_grammar.realize_regions` builds utterances; `analyze_utterance`
   recovers their regions and predicted future samples.
9. `causal_adapter.build_alignment` accepts human expressions paired with source
   offset ranges. It derives overlapping events and their generated regions.
   No adapter input accepts a region identity.
10. Repeated external word sequences are associated with repeated generated
    regions. Generalized translation requires at least 80% token coverage.

## Commands

```bash
python GENERATE_LANGUAGE.py --seed 19020 --vocabulary-scale large --out language.json
python VALIDATE_COMPLETE_LANGUAGE.py language.json
python USE_LANGUAGE.py language.json event ev:000001
```

An external stream adds `--stream stream.json --attestation collection.json`.

The former Concepticon/CLICS/WALS generator remains callable through
`GENERATE_LEGACY_LANGUAGE.py`. It is an adapter and comparison implementation,
not the causal generator.

## Acceptance gates

`tests/test_causal_engine.py` proves:

- interpreted input fields fail closed;
- events contain multiple observed samples and later samples;
- every lexical region replays from numeric evidence;
- every accepted distinction improves held-out reconstruction error;
- constructions and morphology reference learned partition cells;
- productive markers satisfy explicit event-count and host-count thresholds;
- generated utterances round-trip to their internal regions;
- lexicalized roots carry distinct current and historical analyses;
- external expressions do not change canonical language bytes;
- adapter inputs cannot assign `sr:*` identities;
- identical source ranges derive identical regions under changed wording;
- the complete generation trace replays exactly.
