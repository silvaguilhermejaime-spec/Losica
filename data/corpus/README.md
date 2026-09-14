# Corpus input

`losica-vocalsketch-fetch --out PATH` creates a bounded local VocalSketch subset from the public repository.

`losica-vocalsketch-index --dataset-root PATH --out paired_index.json` indexes a full or bounded local release.

The index stores dataset IDs, file paths, speaker IDs, referent IDs, imitation IDs, and source-row provenance. Audio remains under the dataset's original terms.
