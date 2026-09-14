# Externally authored grounding sources for Losica

## Result

This bundle contains 289,480 expressions copied mechanically from five inspected annotation sources. Every expression retains its source repository, external record ID, and pointer to the recording segment, audio sample range, video frame, or object box supplied by that source.

No expression was written, expanded, or paraphrased for Losica.

The catalog is `source_labels.jsonl`. `inputs.lock.json` records repository revisions, file hashes, fields, roles, access limits, and the complete comparison. `build_catalog.py` reconstructs the catalog. `verify_catalog.py` checks the digest, record identities, counts, and target-sentence audit.

The GitHub follow-up added an optional EgoCom path. Its exact word stream yields
24,334 speaker utterances with time ranges, raising a rebuilt extended catalog to
313,814 records. It is not silently added to the locked five-source snapshot:
pass `--include-egocom`, obtain the official media release, and use
`build_egocom_manifest.py` to select one deterministic first-person view per
segment. The transcript is still external metadata and has no route into causal
generation.

## Search scope

The search covered six evidence needs: everyday first-person activity; object/action state change under recorded controls; visible object, attribute, relation, and reference grounding; sound grounding; intention, failure, and future-event wording; multilingual renderings. It inspected checked-out files at exact revisions for 18 GitHub repositories and exact release schemas for Video Localized Narratives, YouCook2, and VATEX. Twenty-three candidates passed into the comparison; five had annotation snapshots with usable distribution terms already present and became the normalized catalog.

This is exhaustive within that operational scope: a candidate needed externally authored text plus either an observation pointer, a causal action/state trace, a multilingual rendering of a pointed observation, or a documented role in parsing the external query. Repositories offering only a captioning model, a README claim without inspectable data fields, a model-written corpus, or an English concept list were excluded from the collected catalog.

## Causal placement

The expression is external metadata. The shared observation is the join key.

1. A recording produces numeric frames.
2. Losica generates events and `sr:*` regions from those frames.
3. A source annotation identifies a range in the same recording.
4. `causal_adapter.build_alignment()` obtains the overlapping events from that range.
5. The adapter associates the externally authored expression with the generated regions used for those events.

The catalog never supplies a region ID, lexical class, semantic primitive, grammatical category, or required word.

## Collected records

| Source | Records | Expression author | Observation pointer | Role |
|---|---:|---|---|---|
| EPIC-KITCHENS-100 | 76,885 | recording participant | video ID, seconds, frames | action description |
| EPIC-SOUNDS | 107,078 | annotator | video ID, seconds, 24 kHz samples | sound description |
| ActivityNet Entities | 46,195 | caption and box annotators | video ID, seconds, sampled frame, token indexes, boxes | video description and visible referents |
| Talk2Car | 9,512 | command author | scene, sample, object box | intended action and referent |
| AudioCaps | 49,810 | human captioner; human-corrected | video ID and ten-second audio interval | sound description |
| **Total** | **289,480** |  |  |  |

These are record counts, not unique-word counts. A record is one JSON line in `source_labels.jsonl`. The locked total is the sum of the five source counts.

| Optional source | Added records | Expression author | Observation pointer | Role |
|---|---:|---|---|---|
| EgoCom | 24,334 | human transcriber | conversation segment, speaker, word-level seconds | embodied conversation |

The EPIC action files in the inspected commit contain 67,217 training rows and 9,668 validation rows after their header rows. The EPIC-SOUNDS source contains 68,090 categorized train/validation descriptions and 39,187 uncategorized rows; 199 uncategorized rows have empty descriptions and are omitted, leaving 107,078 expressions. These rules explain every difference between source row counts and catalog counts.

## Score

The comparison uses an integer score from 0 to 10:

`evidence_link + signal_access + human_wording + setting_coverage + losica_fit`

Each component is 0, 1, or 2. The complete rubric and every component value are in `inputs.lock.json`. There is no 80-versus-81 distinction: only the eleven integer outcomes 0 through 10 exist.

Admission also has a hard gate: grounding labels require human free wording and a pointer to an observation. The score orders admitted sources; it cannot override that gate. This is why WavCaps is rejected despite retaining useful audio pointers.

| Score | Source | Placement | Exact inspected structure | Limitation |
|---:|---|---|---|---|
| 10 | [Ego4D](https://github.com/facebookresearch/Ego4d/tree/4bd10ed40b4f8d8ad26344afc2c8526f7d1dedeb) | primary | official downloader, annotation notebook, Narrations, Goal-Step, Forecasting, synchronized Ego-Exo video | annotations and media require the official license flow |
| 10 | [EgoCom](https://github.com/facebookresearch/EgoCom-Dataset/tree/67f439fcb306acdcfcb8597e2acdf1c3afb8f684) | optional primary conversation | synchronized first-person video/audio, speaker, exact word start/end time | 240p media is a separate 9.5 GB official release |
| 10 | [Clotho through aac-datasets](https://github.com/Labbeti/aac-datasets/tree/631524fb86eef351c1848e42196fbe5cf62442e4) | primary audio | audio file plus five human captions per clip | corpus download is separate from loader code |
| 9 | [EPIC-KITCHENS-100](https://github.com/epic-kitchens/epic-kitchens-100-annotations/tree/ea8b40457a400c3fffa1c7f406ef3dc169cc2522) | primary | `narration_id`, participant/video IDs, narration time, action start/stop, frames, participant narration | kitchen setting |
| 9 | [EPIC-SOUNDS](https://github.com/epic-kitchens/epic-sounds-annotations/tree/57a922f0d352e9429f1ef8a37eee21758dd3a33c) | primary audio | annotation/video IDs, times, exact audio samples, human description | kitchen audio; CC BY-NC 4.0 |
| 9 | [ActivityNet Entities](https://github.com/facebookresearch/ActivityNet-Entities/tree/eb455f7cdd9847cb6dca9f099c84070e2a85f614) | primary visual | segment timestamps, caption tokens, grounded token indexes, sampled frames, `xyxy` boxes | original online videos may be unavailable |
| 9 | [RefEgo](https://github.com/shuheikurita/RefEgo/tree/59799404be1ffeb6206f36c116d3880d2910af66) | primary reference | Ego4D video/clip/image IDs, box, referring expression, target-presence and motion fields | annotation archives are a separate download |
| 9 | [Visual Genome](https://github.com/ranjaykrishna/visual_genome_python_driver/tree/b092f5e52259f7611400eefbc41061e126ef9cba) | primary static visual | region phrase and box; object names and boxes; subject-predicate-object relations; attributes | a still image supplies no event order |
| 9 | [Video Localized Narratives](https://google.github.io/video-localized-narratives/) | primary reference | spoken narrative, word timing, pointer trace, and frame timing | underlying video comes from separate datasets |
| 9 | [AudioCaps through aac-datasets](https://github.com/Labbeti/aac-datasets/tree/631524fb86eef351c1848e42196fbe5cf62442e4) | primary audio | `audiocap_id`, YouTube ID, start time, human caption | some hosted audio may disappear |
| 8 | [Talk2Car](https://github.com/talk2car/Talk2Car/tree/3fde52aee3341312196ab9b2f999337eff0693a0) | primary intention/reference | command token, scene/sample token, command, object token, 2-D box | driving setting; CC BY-NC-SA 4.0 dataset |
| 8 | [YouCook2](https://youcook2.eecs.umich.edu/) | ordered procedures | video and recipe IDs, step start/stop, imperative description; separate box annotations | cooking setting and online-video availability |
| 7 | [DROID](https://github.com/droid-dataset/droid/tree/33ae6a67274f36d2e29525b86f23a56616ef43a7) | causal action/state evidence | synchronized robot observations, actions, episode metadata, language annotations | language annotations are incomplete and commonly episode-level |
| 7 | [BridgeData V2](https://github.com/rail-berkeley/bridge_data_v2/tree/bc60a35b701a12021c8c95e9d8601274d3acd928) | causal action/state evidence | observations, next observations, actions, timestamps, trajectory language | manipulation setting; episode converter required |
| 7 | [VATEX v1.1](https://eric-xw.github.io/vatex-website/download.html) | multilingual display | `videoID`, ten English captions, ten Chinese captions; five paired on each side | clip-level rather than word-time alignment |
| 7 | [VLEP](https://github.com/jayleicn/VideoLanguageFuturePred/tree/1ce739513dc818a858a94939d163fa1aa4238a77) | future-language supplement | premise video interval, two future event strings, accepted candidate | candidate wording is a hypothesis, not a measured state |
| 7 | [How2](https://github.com/srvk/how2-dataset/tree/59c8a7523660514a1a55349c2e4f54ffa9ca3953) | multilingual display | utterance-level English, crowdsourced Portuguese, video/audio features | project reports that most original videos can no longer be downloaded |
| 7 | [ALFRED](https://github.com/askforalfred/alfred/tree/f91f4c0c96c7a29f33d0557f86b0a21035379b3b) | importer test | task and step descriptions, high/low action indexes, frames | simulated household and fixed task system |
| 7 | WavCaps through [aac-datasets](https://github.com/Labbeti/aac-datasets/tree/631524fb86eef351c1848e42196fbe5cf62442e4) | rejected | audio IDs and captions | captions are machine-written or machine-rewritten |
| 6 | [TEACh](https://github.com/alexa/teach/tree/903191e256da866a603d1bbfb21db34e0874392d) | importer test | human-human dialogue, action time, duration, and success in episodes | simulated household |
| 6 | [CALVIN](https://github.com/mees/calvin/tree/fa03f01f19c65920e18cf37398a9ce859274af76) | importer test | episode ranges, task IDs, robot observations/actions, authored expression list | simulation and fixed tasks |
| 5 | [BigVideo-VMT](https://github.com/DeepLearnXMU/BigVideo-VMT/tree/ea6fb2118d1bdb89954fbbcc9ccbd9f2b31402bd) | code reference | VATEX preprocessing and multimodal translation code | repository does not ship the claimed annotation corpus |
| 4 | [Universal Dependencies English EWT](https://github.com/UniversalDependencies/UD_English-EWT/tree/4a4d77f599ea53cc405f85d0cec4b2f14f81d42b) | external parser only | sentence text, token/lemma, part of speech, features, head, dependency, construction and lexical-semantic fields | no recording pointer |
| 4 | [PropBank release](https://github.com/propbank/propbank-release/tree/4abade0b53ce4a181e1d98b3518101c1a44d395a) | external parser only | roleset, predicate, numbered arguments, stand-off token pointers | no recording pointer; some source text requires LDC data |

The official [Visual Genome API](https://visualgenome.org/api/v0/api_endpoint_reference) confirms that region descriptions return a phrase with a region box and that scene graphs return objects, relationships, and attributes. The official [VATEX release](https://eric-xw.github.io/vatex-website/download.html) publishes its exact `videoID`, `enCap`, and `chCap` layout. The official [YouCook2 release](https://youcook2.eecs.umich.edu/download) provides segment annotations and separate object-box annotations. These sources were inspected through their actual schemas or release files, not ranked from names alone.

## Exact Losica transformations

| Source shape | Transformation | Losica target | Test |
|---|---|---|---|
| `video_id,start_timestamp,stop_timestamp,narration` | assign each decoded frame a stable global `source_offset`; convert seconds to the inclusive offsets in the same recording; copy narration unchanged | `causal_stream.make_causal_stream()` then `causal_adapter.build_alignment()` | changing every expression leaves `canonical_causal_language(language)` byte-identical |
| `video_id,start_sample,stop_sample,description` | derive numeric audio windows from the referenced samples; map sample range to generated-frame offsets; copy description unchanged | same two functions | every adapter record names at least one overlapping generated event |
| caption tokens plus token indexes and boxes | join the supplied tokens for the external expression; preserve token indexes, frame index, and box in provenance; map segment times to offsets | source importer then `build_alignment()` | each grounded token index resolves to the source box and frame |
| scene/sample/object token plus command | map the nuScenes sample to one or more causal-stream offsets; preserve command token and object box | source importer then `build_alignment()` | removing command text leaves generated language unchanged; removing its sample pointer makes alignment fail |
| robot observations/actions plus episode language | emit camera/state/action values as numeric frames; assign one offset per synchronized step; map episode label to its offset range | `causal_stream.validate_causal_stream()` then `build_alignment()` | actions, observations, labels, and episode bounds have equal, replayable indexing |
| English/Chinese or English/Portuguese captions for one clip | make two external namespaces point to the same generated event range | two adapter artifacts | the two adapters have the same evidence event IDs while expressions remain source-authored |

Raw pixels, audio samples, proprioception, and controls may feed generation. Human text, class columns, object names, and precomputed language embeddings may feed only external alignment. If a vision feature extractor was trained with text or class labels, its output is excluded from `core_inputs`; use raw signals or a documented label-free encoder.

## Audit of the earlier translation sentence

The audit does not claim that a word occurrence proves a Losica meaning. It reports only whether externally authored wording exists in the gathered catalog.

| Requested distinction | Accepted exact case-folded token forms | Records containing at least one accepted token |
|---|---|---:|
| bread | `bread` | 637 |
| purchase | `buy`, `buys`, `buying`, `bought` | 13 |
| same-day reference | `today` | 11 |
| inability | `cannot`, `can't`, `couldn't`, `unable` | 8 |
| failed result | `fail`, `fails`, `failed`, `failing` | 41 |
| stated intention | `intend*`, `intention*`, `want*`, `plan*` using the exact forms listed in `verification.json` | 228 |

The numerator for each value is the number of catalog records containing an accepted exact token. The denominator is 289,480 catalog records. The bundle does not convert these to percentages because an EPIC observed action, an AudioCaps sound description, and a Talk2Car command have different evidence roles. `verification.json` gives the count by source so they cannot be silently combined as equivalent evidence.

These occurrences solve label authorship. They do not establish that the current Losica stream supports the complete sentence. A translation becomes licensed only after the matching recordings are imported, Losica independently retains the relevant distinctions during communication, and repeated range alignment reaches the adapter's evidence threshold.

## Rebuild and verify

From the directory containing this bundle and the inspected repository snapshots:

```bash
python build_catalog.py \
  --repos ../../research_repos \
  --out source_labels.jsonl \
  --summary catalog_summary.json

python verify_catalog.py \
  --catalog source_labels.jsonl \
  --lock inputs.lock.json \
  --repos ../../research_repos \
  --out verification.json
```

Add `--include-egocom` to build the 313,814-record extended catalog. This is an
extension, so do not verify it against the unchanged five-source lock digest.

Expected result:

```json
The exact record count and digest are stored in `verification.json`.
```

## Files intentionally absent

- Ego4D, DROID, BridgeData V2, RefEgo, Clotho, VATEX, YouCook2, Video Localized Narratives, and VLEP annotations are identified but not copied because their official access, license, agreement, or base-recording flow must be followed by the user who obtains them.
- WavCaps expressions are absent because the inspected loader identifies them as machine annotated.
- Universal Dependencies and PropBank sentences are absent from the grounding catalog because they have no pointer into a shared observation.
- Test labels withheld by their dataset authors remain withheld.

This preserves source terms and prevents ungrounded text from becoming semantic evidence.
