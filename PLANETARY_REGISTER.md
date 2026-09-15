# Reversible planetary register

## What this expansion is

This is a working, finite scientific register—not a claim that Losica is now an
unrestricted natural language. It can state and recover 22 scalar facts from
the pinned `losica-131757842` physical-climate world state. The source archive
has SHA-256
`8cf16f9cb6220dd5759da752c8f719d1561bba97bf63bd56f141716b45c0b0e1`.

The archive explicitly excludes inhabitants, culture, language, acoustics, and
sensory categories. The register therefore does not manufacture them. Its only
new idiosyncrasy is functional: every claim begins by saying how the value
entered the model.

## Claim grammar

| Slot | Required burden |
|---|---|
| `CLAIM` | Opens exactly one typed scalar claim. |
| `EVIDENCE` | Says `sampled`, `derived`, `modeled`, `conditioned`, or `uncertain`. |
| `SUBJECT` | Identifies the host star or target planet. |
| `QUANTITY` | Selects one exact JSON field; it carries no value or unit. |
| `NUMBER` | Preserves the exact decimal spelling, or an explicit null. |
| `UNIT` | States the unit independently of the magnitude. |
| `MODEL` | Names the provenance-model registry entry. |
| `END` | Closes the claim. |

These roles are positions inside the existing `root` and `clause_operator`
classes. The register adds no grammatical class. Each generated word has one
stable semantic ID; labels such as “mean solar day” do not control its form.

## Exact example

The source record is:

```json
{
  "evidence_id": "evidence:derived",
  "subject_id": "subject:planet",
  "quantity_id": "quantity:mean_solar_day",
  "value": "8.556787177492277",
  "unit_id": "unit:hour",
  "model_id": "model:ORB1"
}
```

Compact Losica:

```text
liptam makpip mimtun luprat 8.556787177492277 miktim tamtuk punrar
```

Phonemic IPA, with the written numeral read digit by digit:

```text
/lip.tam mak.pip mim.tun lup.rat kit.kʼir rak.lik i.mir i.mir kʼa.lin rat.lum kit.kʼir rat.lum mut.kik rat.lum rat.lum uk.nik tit.lin kʼa.kar kʼa.kar rat.lum rat.lum mik.tim tam.tuk pun.rar/
```

| Form | Role | Exact meaning and burden |
|---|---|---|
| `liptam` | claim | Opens one typed scalar claim. |
| `makpip` | evidence | Derived: calculated from stated inputs under the named model. |
| `mimtun` | subject | The target planet at `/target_planet`. |
| `luprat` | quantity | The field `/target_planet/orbit/mean_solar_day_hours`; no value or unit is bundled into it. |
| `8.556787177492277` | number | This exact decimal sequence; no rounding or unit is implicit. |
| `miktim` | unit | Hour; no magnitude is bundled into it. |
| `tamtuk` | model | `ORB1`, the archived Keplerian two-body model entry. |
| `punrar` | end | Closes the claim. |

The full spoken-number form replaces the numeral with 17 reversible digit and
decimal-point words. It is lossless but intentionally not the default written
form.

## Inverse and failure behavior

For every included fact, both compact and fully spoken encoding satisfy:

```text
decode(encode(record)) == record
```

The encoder rejects binary floating-point inputs; callers must provide the
exact decimal string. The decoder rejects unknown forms, missing boundaries,
invalid decimal syntax, category swaps, null values without `uncertain`, and
uncertain values without null. Artifact mutation is detected by a canonical
SHA-256 digest.

## Evidence words do not overclaim

- `sampled` means a retained or generated draw; it does not imply calibration.
- `derived` means calculated from other inputs under the named model.
- `modeled` means a model output, not a direct observation.
- `conditioned` means selected or altered by a declared conditioning step.
- `uncertain` means the source commits to no value; the null is preserved.

## Build and inspect

```bash
python BUILD_PLANETARY_REGISTER.py --out planetary-register.json
python USE_PLANETARY_REGISTER.py planetary-register.json say fact:mean_solar_day
python USE_PLANETARY_REGISTER.py planetary-register.json say fact:mean_solar_day --spoken-numbers
python USE_PLANETARY_REGISTER.py planetary-register.json analyze "LOSICA CLAIM"
```

The `say` and `analyze` commands return the decoded record, source pointer, IPA,
and a word-by-word burden table. Unknown material fails closed rather than being
assigned a plausible-sounding meaning.
