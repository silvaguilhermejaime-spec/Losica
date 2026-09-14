# Third-party sources and boundaries

The bundled snapshot records upstream versions and commit identities. Full datasets, model checkpoints, and external executables follow their upstream distribution terms and enter through file/CLI adapters.

| Source | Version used | License/distribution boundary | Losica mechanism |
|---|---:|---|---|
| Grambank | 1.0 | CC-BY 4.0 | imports original parameter/observation IDs and control metadata |
| WALS Online | 2020.4 | CC-BY 4.0 | imports chapters/features and builds joint order profiles |
| UniMorph | schema + language datasets | Dataset-specific upstream licenses | imports feature-bundle paradigms |
| Concepticon | 3.4.0 | CC-BY 4.0; DOI `10.5281/zenodo.21373838` | supplies stable semantic-probe identifiers and downstream display annotations |
| CLICS4 | 1.0 | CC-BY 4.0; DOI `10.5281/zenodo.16900179` | supplies structural colexification evidence through language, parameter, Concepticon-ID, and form relations |
| PHOIBLE | 2.0 | Data files carry the MIT license; repository code carries GPL-3.0 | supplies distinctive features and inventory counts |
| Universal Dependencies | 2.18 interface | Treebank-specific licenses | imports CoNLL-U construction templates |
| DELPH-IN Grammar Matrix | external checkout | Upstream license | supplies an optional typed-coverage comparison |
| DELPH-IN Grammary | 2026 interface | Upstream grammar licenses | supplies optional implemented-grammar comparisons |
| CLDF / pycldf | current / 2.1 | Apache-2.0 / upstream package license | writes and validates interoperable tables |
| QBV | Greif et al. 2024 | External code/checkpoint | supplies dual-encoder rankings |
| RWCP-SSD-Onomatopoeia | Okamoto et al. 2020 | Corpus remains local under upstream terms | supplies worker/confidence/acceptance population evidence |
| ESC-50-Voice | 2024 | DOI `10.5281/zenodo.11385662`; corpus remains external | supplies paired recordings and speaker IDs |
| VocalSketch | CHI 2015 | Corpus remains external | supplies vocal responses and identification evidence |
| Vocal Imitation Set | DCASE 2018 | DOI `10.5281/zenodo.1340763`; corpus remains external | supplies paired imitations and sound classes |
| Allosaurus | ICASSP 2020 | External model/checkpoint | supplies uncertain phone hypotheses |
| Brassica | external executable | Upstream license | exchanges staged rules, forms, and traces |
| Lexurgy | external executable | GPL-3.0 | exchanges regular sound-change rules, forms, and traces |
| SakanaAI LanguageEvolution | 2026 external checkout | Upstream license | exchanges populations, networks, generations, lexicons, and morphology |
| Babel / Fluid Construction Grammar | external checkout | Upstream license | exchanges form–meaning construction records |
| Facebook Research EGG | external framework | Upstream license | exchanges emergent signaling experiments separately from natural-language state |
| Kirby, Cornish & Smith | 2008 | DOI `10.1073/pnas.0707835105` | supplies the empirical basis for iterated transmission |
| Bybee | 2006/2011 publications | Publications cited in generated provenance | supplies measurable usage and grammaticalization variables |
| Baayen and later productivity work | 1992–1999+ publications | Publications cited in generated provenance | supplies `N`, `V`, `n1`, potential/expanding productivity, and generalization measures |
| ConlangCrafter | ACL 2026 Oral | External benchmark/code terms | supplies the completeness comparison boundary |

The compact snapshot contains attributed derived subsets and aggregates selected by `tools/build_empirical_snapshot.py`. Audio examples in `data/` are Losica fixtures. The archive packages adapter code and fixture data; full external audio corpora and learned checkpoints remain separately distributed.

## Publication ledger

- Skirgård et al., *Grambank reveals the importance of genealogical constraints on linguistic diversity and highlights the impact of language loss*; dataset repository `grambank/grambank`.
- Dryer & Haspelmath, eds., *The World Atlas of Language Structures Online*, release 2020.4.
- List et al., Concepticon 3.4.0, DOI `10.5281/zenodo.21373838`.
- Tjuka, Forkel, Rzymski & List, *CLICS4: An Improved Database of Cross-Linguistic Colexifications*, DOI `10.5281/zenodo.16900179`.
- Moran & McCloy, eds., *PHOIBLE 2.0*.
- Bender, Flickinger & Oepen, DELPH-IN Grammar Matrix; Bond & Flickinger 2026, DELPH-IN Grammary.
- Greif, Schmid, Primus & Widmer 2024, *Improving Query-by-Vocal Imitation with Contrastive Learning and Audio Pretraining*.
- Okamoto et al. 2020, RWCP-SSD-Onomatopoeia; Okamoto et al. 2024, ESC-50-Voice, DOI `10.5281/zenodo.11385662`.
- Cartwright & Pardo 2015, VocalSketch; Kim, Ghei, Pardo & Duan 2018, Vocal Imitation Set, DOI `10.5281/zenodo.1340763`.
- Li et al. 2020, *Universal Phone Recognition with a Multilingual Allophone System*.
- Kulanthaivelu & Sproat 2026, *Agent-based models for the evolution of morphological alternation patterns*.
- Kirby, Cornish & Smith 2008, *Cumulative cultural evolution in the laboratory: An experimental approach to the origins of structure in human language*, DOI `10.1073/pnas.0707835105`.
- Bybee 2006, *From Usage to Grammar: The Mind's Response to Repetition*, DOI `10.1353/lan.2006.0186`; Bybee 2011, *Usage-Based Theory and Grammaticalization*.
- Baayen 1992/1993/1994; Baayen & Renouf 1996; Plag, Dalton-Puffer & Baayen 1999; subsequent hapax-based productivity work.
- Alper, Yanuka, Giryes & Beguš 2026, *ConlangCrafter: Constructing Languages with a Multi-Hop LLM Pipeline*.
