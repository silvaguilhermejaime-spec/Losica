# Source notice

`source_labels.jsonl` is a mechanical normalization of annotation text and observation pointers from the following upstream works. It contains no source video, image, or audio.

- EPIC-KITCHENS-100 annotations, EPIC-KITCHENS team, [CC BY-NC 4.0](https://github.com/epic-kitchens/epic-kitchens-100-annotations/blob/ea8b40457a400c3fffa1c7f406ef3dc169cc2522/license.txt).
- EPIC-SOUNDS annotations, Huh, Chalk, Kazakos, Damen, and Zisserman, [CC BY-NC 4.0](https://github.com/epic-kitchens/epic-sounds-annotations/blob/57a922f0d352e9429f1ef8a37eee21758dd3a33c/README.md#license).
- ActivityNet Entities annotations, Zhou, Kalantidis, Chen, Corso, and Rohrbach, repository [license](https://github.com/facebookresearch/ActivityNet-Entities/blob/eb455f7cdd9847cb6dca9f099c84070e2a85f614/LICENSE). Descriptions originate in ActivityNet Captions; source-media terms remain separate.
- Talk2Car annotations, Deruyttere, Vandenhende, Grujicic, Van Gool, and Moens, [CC BY-NC-SA 4.0](https://github.com/talk2car/Talk2Car/blob/3fde52aee3341312196ab9b2f999337eff0693a0/LICENSE).
- AudioCaps metadata distributed in `aac-datasets`, Labbé software [MIT license](https://github.com/Labbeti/aac-datasets/blob/631524fb86eef351c1848e42196fbe5cf62442e4/LICENSE); AudioCaps was created by Kim, Kim, Lee, and Kim. Source-media terms remain separate.

The normalization changes field names and JSON layout. It preserves each expression exactly, except that ActivityNet's supplied token array is joined with single spaces. Each record identifies its upstream source and source file.

The presence of an annotation in this research bundle does not grant rights to its underlying recording. Follow every upstream dataset's access, attribution, noncommercial, and share-alike terms. Commercial use requires a source-by-source rights review.
