"""Validated worked derivations copied from daughter-language descriptions."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .validation import identifier, keys, label, read_json, require, strings, text


ATTESTATION_STATUSES = frozenset({"attested", "not_printed"})
ENTRY_COVERAGE = frozenset({"both_descriptions", "one_description"})
NOTATIONS = frozenset({"reconstructed", "phonemic", "phonetic", "orthographic"})
RECONSTRUCTION_STATUSES = frozenset({"provisional_mapping", "established"})
MEANING_STATUSES = frozenset({"not_supplied", "supplied"})


@dataclass(frozen=True)
class FormStage:
    form: str
    notation: str


@dataclass(frozen=True)
class Attestation:
    status: str
    source_id: str | None
    source_section: str | None
    chain: tuple[FormStage, ...]


@dataclass(frozen=True)
class HistoricalExample:
    id: str
    reconstruction_form: str
    reconstruction_stage: str
    reconstruction_status: str
    meaning: str | None
    meaning_status: str
    morphology: str
    related_to: str | None
    coverage: str
    attestations: Mapping[str, Attestation]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class HistoricalExamples:
    schema: str
    sources: Mapping[str, Mapping[str, str]]
    entries: tuple[HistoricalExample, ...]

    @property
    def shared_input_examples(self):
        return tuple(entry for entry in self.entries if entry.coverage == "both_descriptions")


def _optional_text(value, context):
    if value is None:
        return None
    return text(value, context)


def _source(value):
    keys(value, {"id", "title", "language", "file", "scope"}, context="historical-example source")
    source_id = identifier(value["id"], "historical-example source id")
    return source_id, MappingProxyType({
        "title": label(value["title"], f"source {source_id} title"),
        "language": label(value["language"], f"source {source_id} language"),
        "file": text(value["file"], f"source {source_id} file"),
        "scope": text(value["scope"], f"source {source_id} scope"),
    })


def _form_stage(value, context):
    keys(value, {"form", "notation"}, context=context)
    notation = text(value["notation"], f"{context} notation")
    require(notation in NOTATIONS, f"{context}: unknown notation {notation!r}")
    return FormStage(text(value["form"], f"{context} form"), notation)


def _attestation(value, branch_id, sources, reconstruction_form):
    context = f"attestation {branch_id}"
    keys(value, {"status", "source_id", "source_section", "chain"}, context=context)
    status = text(value["status"], f"{context} status")
    require(status in ATTESTATION_STATUSES, f"{context}: unknown status {status!r}")
    require(isinstance(value["chain"], list), f"{context}: chain must be a list")
    require(len(value["chain"]) <= 24, f"{context}: chain exceeds 24 stages")
    chain = tuple(
        _form_stage(stage, f"{context} chain stage {index}")
        for index, stage in enumerate(value["chain"], 1)
    )
    source_id = _optional_text(value["source_id"], f"{context} source_id")
    source_section = _optional_text(value["source_section"], f"{context} source_section")

    if status == "attested":
        require(source_id in sources, f"{context}: unknown source {source_id!r}")
        require(source_section is not None, f"{context}: source section required")
        require(len(chain) >= 2, f"{context}: attested chain requires at least two stages")
        require(chain[0] == FormStage(reconstruction_form, "reconstructed"),
                f"{context}: chain must begin with the entry reconstruction")
        require(any(stage.notation == "phonemic" for stage in chain),
                f"{context}: chain requires a phonemic daughter outcome")
    else:
        require(source_id is None and source_section is None and not chain,
                f"{context}: missing evidence must leave source and chain empty")

    return Attestation(status, source_id, source_section, chain)


def _entry(value, sources, branch_ids):
    keys(
        value,
        {
            "id", "reconstruction", "meaning", "meaning_status", "morphology",
            "related_to", "coverage", "attestations", "notes",
        },
        context="historical example",
    )
    entry_id = identifier(value["id"], "historical example id")
    reconstruction = value["reconstruction"]
    keys(reconstruction, {"form", "stage", "status"}, context=f"entry {entry_id} reconstruction")
    reconstruction_form = text(reconstruction["form"], f"entry {entry_id} reconstruction form")
    reconstruction_status = text(reconstruction["status"], f"entry {entry_id} reconstruction status")
    require(
        reconstruction_status in RECONSTRUCTION_STATUSES,
        f"entry {entry_id}: unknown reconstruction status {reconstruction_status!r}",
    )

    meaning_status = text(value["meaning_status"], f"entry {entry_id} meaning status")
    require(meaning_status in MEANING_STATUSES,
            f"entry {entry_id}: unknown meaning status {meaning_status!r}")
    meaning = _optional_text(value["meaning"], f"entry {entry_id} meaning")
    require((meaning is None) == (meaning_status == "not_supplied"),
            f"entry {entry_id}: meaning and meaning status disagree")

    require(isinstance(value["attestations"], dict), f"entry {entry_id}: attestations object required")
    require(set(value["attestations"]) == branch_ids,
            f"entry {entry_id}: attestations must cover every branch")
    attestations = {
        branch_id: _attestation(attestation, branch_id, sources, reconstruction_form)
        for branch_id, attestation in value["attestations"].items()
    }
    attested_count = sum(item.status == "attested" for item in attestations.values())
    expected_coverage = (
        "both_descriptions" if attested_count == len(branch_ids) else "one_description"
    )
    coverage = text(value["coverage"], f"entry {entry_id} coverage")
    require(coverage in ENTRY_COVERAGE, f"entry {entry_id}: unknown coverage {coverage!r}")
    require(coverage == expected_coverage, f"entry {entry_id}: coverage disagrees with attestations")

    notes = strings(value["notes"], f"entry {entry_id} notes", max_items=16)
    return HistoricalExample(
        entry_id,
        reconstruction_form,
        label(reconstruction["stage"], f"entry {entry_id} reconstruction stage"),
        reconstruction_status,
        meaning,
        meaning_status,
        text(value["morphology"], f"entry {entry_id} morphology"),
        _optional_text(value["related_to"], f"entry {entry_id} related_to"),
        coverage,
        MappingProxyType(attestations),
        notes,
    )


def load_historical_examples(path, family_history=None):
    data = read_json(path)
    keys(data, {"schema", "sources", "entries"}, context="historical worked-example register")
    schema = text(data["schema"], "historical worked-example register schema")
    require(schema == "losica-historical-examples/1", "unsupported historical worked-example register schema")

    require(isinstance(data["sources"], list), "historical-example sources must be a list")
    source_rows = tuple(_source(value) for value in data["sources"])
    sources = dict(source_rows)
    require(len(sources) == len(source_rows), "duplicate historical-example source id")

    branch_ids = (
        set(family_history.branches)
        if family_history is not None
        else {"komuheftic", "sisengwigwo"}
    )
    require(isinstance(data["entries"], list), "historical examples must be a list")
    require(1 <= len(data["entries"]) <= 10000, "historical worked-example register requires 1..10000 entries")
    entries = tuple(_entry(value, sources, branch_ids) for value in data["entries"])
    entry_ids = {entry.id for entry in entries}
    require(len(entry_ids) == len(entries), "duplicate historical example id")
    for entry in entries:
        if entry.related_to is not None:
            require(entry.related_to in entry_ids and entry.related_to != entry.id,
                    f"entry {entry.id}: invalid related_to reference")

    return HistoricalExamples(schema, MappingProxyType(sources), entries)
