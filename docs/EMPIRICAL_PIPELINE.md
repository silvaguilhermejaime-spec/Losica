# Empirical data pipeline

## Structural and lexical evidence

Pinned upstream CLDF and CSV files enter `tools/build_empirical_snapshot.py`. Original Grambank and WALS observation IDs enter aggregates and joint profiles together with family, macroarea, and missing-data information. Concepticon IDs enter a ranked concept inventory. CLICS nodes and edges enter weighted colexification evidence. PHOIBLE inventories enter segment-feature and prevalence audits. The operation writes `data/empirical_snapshot_v0_21.json`, whose upstream versions and commits bind each derived record.

The direct generator samples complete WALS 81A/85A/86A/87A/89A vectors. WALS 20A/21A/22A/23A/24A/25A/49A/101A/102A distributions audit exponence, synthesis, marking locus, case, pronoun expression, and agreement. Grambank aggregates condition a compatible morphology profile. Each selected property names its executor.

## Environmental and human-imitation evidence

```text
physical event and propagated pressure waveform
→ query WAV plus SHA-256
→ QBV-style dual-encoder ranking over a named corpus index
→ speaker-linked human vocal imitations
→ Allosaurus phone-hypothesis distribution
→ PHOIBLE-feature distance into the active Losica inventory
→ phonotactically licensed lexical candidate
→ conventional lexeme with complete evidence binding
```

The QBV ranking contract binds the query waveform, model/checkpoint, corpus/index, preprocessing, scores, and imitation identities. Alternative phone hypotheses remain available after mapping. RWCP confidence and acceptance judgments remain population observations. ESC-50-Voice, VocalSketch, and Vocal Imitation Set records retain speakers and paired source identities. CLICS semantic association occupies a separate provenance channel.

The archive carries a deterministic waveform/ranking fixture for direct generation. Full corpora and learned checkpoints enter through the same tested import contracts under their upstream distribution terms.
