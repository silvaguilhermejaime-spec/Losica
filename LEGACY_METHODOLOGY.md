# Losica 0.25 methodology

## Generation state

A seed and normalized empirical evidence produce one deterministic language state. WALS joint profiles provide correlated constituent-order evidence. Grambank observations weight compatible morphosyntactic profiles. PHOIBLE supplies segment-feature comparisons. Concepticon IDs provide stable semantic probes. CLICS supplies weighted semantic-association evidence for lexical colexification. Each sampled choice records candidates, weights, source IDs, method, and seed.

## Lexicalization

The core lexicon addresses concepts by stable probe ID. CLICS-weighted sampling associates compatible probes into generated lexical regions. Phonotactic allocation supplies conventional forms. The acoustic channel supplies a form through the paired-imitation fixture. Generated participant-reference cells, numeral atoms, and grammatical functions receive forms through the active phonological inventory.

The final language build uses 512 semantic probes. Productive morphology materializes category-changing derivatives across eligible open-class roots: verbal nominalization, nominal property formation, and property-to-adverb formation. The derivation API retains valency-changing processes for recursive lexical development.

## Reference and agreement

Participant reference is represented through speaker membership, addressee membership, and cardinality. The seed samples a partition over that semantic space. Subject indexing is sampled separately and maps participant configurations into generated agreement cells. Surface analysis retains readings licensed by syncretic agreement.

## Numerals

The seed samples a cardinal numeral radix and coefficient/power order. The generator creates lexical atoms for the radix digits and powers. Arithmetic composition realizes cardinal values through those atoms. Surface analysis composes the same atoms back into numeric values. The generated profile records the supported range.

## Grammar and realization

Typed semantic graphs contain predicates, participant roles, adjunct roles, embedded content, and grammatical features. The executor maps those structures through lexical valency, generated case/adposition strategies, morphology, constituent order, complement placement, question placement, reference morphology, numeral composition, and prosody.

Entity adjuncts cover location, source, goal, instrument, beneficiary, time, and manner. Clause-valued time and manner arguments use the generated subordinate-clause strategy. CONTENT uses the complement strategy. Construction realization produces phonemic tokens, orthographic tokens, morpheme traces, feature bundles, dependency relations, phrase prominence, and a display semantic summary.

Semantic entity records carry distinctions that participate in the generated realization. Contextual distinctions enter discourse state or external adapters rather than receiving automatic grammatical values.

## Surface analysis

The analyzer starts from an orthographic Losica expression and the generated language snapshot. Orthographic words are matched against generated lexical forms and inflectional paradigms. Case, adpositions, finite morphology, participant-reference cells, numeral atoms, function forms, word order, and construction markers constrain semantic reconstruction. The result is a set of licensed semantic readings.

Release validation requires every bundled construction meaning to appear in that set. Capability probes add nested-event composition and multi-atom numeral composition.

## Source-language adapters

Adapters map external utterances into typed semantic messages and call the generated-language executor. The generated state enters adapters as an immutable snapshot. Canonical language hashing remains invariant across display locale changes and randomized display strings.

`empirical_source_v0_26.json` stores the structural source registry, stable evidence identifiers, numeric observations, and normalized typological codes. `empirical_core_v0_26.json` is compiled from that source. `display_en_v0_26.json` supplies English labels and documentation after generation.

## Finalization and export

`FINALIZE_LANGUAGE.py` creates the large lexical state, validates it, and exports the language JSON together with grammar, dictionary, reference, numeral, construction, orthography, paradigm, provenance, interlinear, and CLDF resources. `FINAL_LANGUAGE.json` records the final seed, counts, generated system IDs, validation status, and content hash.

Generation zero initializes chronological state. Usage history, sound-change adapters, population evolution, and grammaticalization operate on generated forms, IDs, structures, frequencies, and lineage links.

## Lexical semantic regions

The semantic network stage receives stable probe identifiers and numeric topology evidence. Seeded graph partitioning produces Losica-internal semantic regions identified as `sr:*`. A region may contain several external probes, and a probe may anchor several regions. Seed 19020 currently yields 294 regions from 512 probes, with 177 multi-probe regions and 43 overlapping probes. Forms and grammatical behavior are generated for the internal regions. Display adapters attach human-language labels after the linguistic state exists.
