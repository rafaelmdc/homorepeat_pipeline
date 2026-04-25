"""Shared fieldnames and row validators for the publish-contract v2 tables."""

from __future__ import annotations

from typing import Callable, Mapping, Sequence

from homorepeat.io.tsv_io import ContractError


GENOMES_FIELDNAMES = [
    "batch_id",
    "genome_id",
    "source",
    "accession",
    "genome_name",
    "assembly_type",
    "taxon_id",
    "assembly_level",
    "species_name",
    "notes",
]
TAXONOMY_FIELDNAMES = ["taxon_id", "taxon_name", "parent_taxon_id", "rank", "source"]
MATCHED_SEQUENCES_FIELDNAMES = [
    "batch_id",
    "sequence_id",
    "genome_id",
    "sequence_name",
    "sequence_length",
    "gene_symbol",
    "transcript_id",
    "isoform_id",
    "assembly_accession",
    "taxon_id",
    "source_record_id",
    "protein_external_id",
    "translation_table",
    "gene_group",
    "linkage_status",
    "partial_status",
]
MATCHED_PROTEINS_FIELDNAMES = [
    "batch_id",
    "protein_id",
    "sequence_id",
    "genome_id",
    "protein_name",
    "protein_length",
    "gene_symbol",
    "translation_method",
    "translation_status",
    "assembly_accession",
    "taxon_id",
    "gene_group",
    "protein_external_id",
]
REPEAT_CALL_CODON_USAGE_FIELDNAMES = [
    "call_id",
    "method",
    "repeat_residue",
    "sequence_id",
    "protein_id",
    "amino_acid",
    "codon",
    "codon_count",
    "codon_fraction",
]
REPEAT_CONTEXT_FIELDNAMES = [
    "call_id",
    "protein_id",
    "sequence_id",
    "aa_left_flank",
    "aa_right_flank",
    "nt_left_flank",
    "nt_right_flank",
    "aa_context_window_size",
    "nt_context_window_size",
]
DOWNLOAD_MANIFEST_FIELDNAMES = [
    "batch_id",
    "assembly_accession",
    "download_status",
    "package_mode",
    "download_path",
    "rehydrated_path",
    "checksum",
    "file_size_bytes",
    "download_started_at",
    "download_finished_at",
    "notes",
]
NORMALIZATION_WARNINGS_FIELDNAMES = [
    "warning_code",
    "warning_scope",
    "warning_message",
    "batch_id",
    "genome_id",
    "sequence_id",
    "protein_id",
    "assembly_accession",
    "source_file",
    "source_record_id",
]
ACCESSION_STATUS_FIELDNAMES = [
    "assembly_accession",
    "batch_id",
    "download_status",
    "normalize_status",
    "translate_status",
    "detect_status",
    "finalize_status",
    "terminal_status",
    "failure_stage",
    "failure_reason",
    "n_genomes",
    "n_proteins",
    "n_repeat_calls",
    "notes",
]
ACCESSION_CALL_COUNTS_FIELDNAMES = [
    "assembly_accession",
    "batch_id",
    "method",
    "repeat_residue",
    "detect_status",
    "finalize_status",
    "n_repeat_calls",
]

TABLE_FIELDNAMES: dict[str, list[str]] = {
    "genomes.tsv": GENOMES_FIELDNAMES,
    "taxonomy.tsv": TAXONOMY_FIELDNAMES,
    "matched_sequences.tsv": MATCHED_SEQUENCES_FIELDNAMES,
    "matched_proteins.tsv": MATCHED_PROTEINS_FIELDNAMES,
    "repeat_call_codon_usage.tsv": REPEAT_CALL_CODON_USAGE_FIELDNAMES,
    "repeat_context.tsv": REPEAT_CONTEXT_FIELDNAMES,
    "download_manifest.tsv": DOWNLOAD_MANIFEST_FIELDNAMES,
    "normalization_warnings.tsv": NORMALIZATION_WARNINGS_FIELDNAMES,
    "accession_status.tsv": ACCESSION_STATUS_FIELDNAMES,
    "accession_call_counts.tsv": ACCESSION_CALL_COUNTS_FIELDNAMES,
}


def validate_genome_row(row: Mapping[str, object]) -> None:
    _validate_required_fields(
        row,
        fieldnames=GENOMES_FIELDNAMES,
        required_fields=("batch_id", "genome_id", "source", "accession", "taxon_id"),
        label="genomes.tsv",
    )


def validate_taxonomy_row(row: Mapping[str, object]) -> None:
    _validate_required_fields(
        row,
        fieldnames=TAXONOMY_FIELDNAMES,
        required_fields=("taxon_id", "taxon_name", "rank", "source"),
        label="taxonomy.tsv",
    )


def validate_matched_sequence_row(row: Mapping[str, object]) -> None:
    _validate_required_fields(
        row,
        fieldnames=MATCHED_SEQUENCES_FIELDNAMES,
        required_fields=("batch_id", "sequence_id", "genome_id", "sequence_name", "sequence_length"),
        label="matched_sequences.tsv",
    )
    _parse_int(row, fieldname="sequence_length", label="matched_sequences.tsv", minimum=1)
    _parse_int(row, fieldname="translation_table", label="matched_sequences.tsv", minimum=1, allow_empty=True)


def validate_matched_protein_row(row: Mapping[str, object]) -> None:
    _validate_required_fields(
        row,
        fieldnames=MATCHED_PROTEINS_FIELDNAMES,
        required_fields=("batch_id", "protein_id", "sequence_id", "genome_id", "protein_length"),
        label="matched_proteins.tsv",
    )
    _parse_int(row, fieldname="protein_length", label="matched_proteins.tsv", minimum=1)


def validate_repeat_call_codon_usage_row(row: Mapping[str, object]) -> None:
    _validate_required_fields(
        row,
        fieldnames=REPEAT_CALL_CODON_USAGE_FIELDNAMES,
        required_fields=tuple(REPEAT_CALL_CODON_USAGE_FIELDNAMES),
        label="repeat_call_codon_usage.tsv",
    )
    repeat_residue = str(row.get("repeat_residue", "")).strip().upper()
    amino_acid = str(row.get("amino_acid", "")).strip().upper()
    codon = str(row.get("codon", "")).strip().upper().replace("U", "T")
    if len(repeat_residue) != 1:
        raise ContractError("repeat_call_codon_usage.tsv repeat_residue must be one amino-acid symbol")
    if len(amino_acid) != 1:
        raise ContractError("repeat_call_codon_usage.tsv amino_acid must be one amino-acid symbol")
    if len(codon) != 3:
        raise ContractError("repeat_call_codon_usage.tsv codon must be exactly three nucleotides")
    _parse_int(row, fieldname="codon_count", label="repeat_call_codon_usage.tsv", minimum=1)
    _parse_float(row, fieldname="codon_fraction", label="repeat_call_codon_usage.tsv", minimum=0.0, maximum=1.0)


def validate_repeat_context_row(row: Mapping[str, object]) -> None:
    _validate_required_fields(
        row,
        fieldnames=REPEAT_CONTEXT_FIELDNAMES,
        required_fields=("call_id", "protein_id", "sequence_id", "aa_context_window_size", "nt_context_window_size"),
        label="repeat_context.tsv",
    )
    aa_window = _parse_int(row, fieldname="aa_context_window_size", label="repeat_context.tsv", minimum=0)
    nt_window = _parse_int(row, fieldname="nt_context_window_size", label="repeat_context.tsv", minimum=0)

    aa_left = str(row.get("aa_left_flank", "")).strip().upper()
    aa_right = str(row.get("aa_right_flank", "")).strip().upper()
    nt_left = str(row.get("nt_left_flank", "")).strip().upper().replace("U", "T")
    nt_right = str(row.get("nt_right_flank", "")).strip().upper().replace("U", "T")

    if len(aa_left) > aa_window or len(aa_right) > aa_window:
        raise ContractError("repeat_context.tsv amino-acid flank length exceeds aa_context_window_size")
    if len(nt_left) > nt_window or len(nt_right) > nt_window:
        raise ContractError("repeat_context.tsv nucleotide flank length exceeds nt_context_window_size")


def validate_download_manifest_row(row: Mapping[str, object]) -> None:
    _validate_required_fields(
        row,
        fieldnames=DOWNLOAD_MANIFEST_FIELDNAMES,
        required_fields=("batch_id", "assembly_accession", "download_status", "package_mode"),
        label="download_manifest.tsv",
    )
    _parse_int(row, fieldname="file_size_bytes", label="download_manifest.tsv", minimum=0, allow_empty=True)


def validate_normalization_warning_row(row: Mapping[str, object]) -> None:
    _validate_required_fields(
        row,
        fieldnames=NORMALIZATION_WARNINGS_FIELDNAMES,
        required_fields=("warning_code", "warning_scope", "warning_message"),
        label="normalization_warnings.tsv",
    )


def validate_accession_status_row(row: Mapping[str, object]) -> None:
    _validate_required_fields(
        row,
        fieldnames=ACCESSION_STATUS_FIELDNAMES,
        required_fields=(
            "assembly_accession",
            "batch_id",
            "download_status",
            "normalize_status",
            "translate_status",
            "detect_status",
            "finalize_status",
            "terminal_status",
        ),
        label="accession_status.tsv",
    )
    _parse_int(row, fieldname="n_genomes", label="accession_status.tsv", minimum=0)
    _parse_int(row, fieldname="n_proteins", label="accession_status.tsv", minimum=0)
    _parse_int(row, fieldname="n_repeat_calls", label="accession_status.tsv", minimum=0)


def validate_accession_call_count_row(row: Mapping[str, object]) -> None:
    _validate_required_fields(
        row,
        fieldnames=ACCESSION_CALL_COUNTS_FIELDNAMES,
        required_fields=(
            "assembly_accession",
            "batch_id",
            "method",
            "repeat_residue",
            "detect_status",
            "finalize_status",
            "n_repeat_calls",
        ),
        label="accession_call_counts.tsv",
    )
    _parse_int(row, fieldname="n_repeat_calls", label="accession_call_counts.tsv", minimum=0)


TABLE_ROW_VALIDATORS: dict[str, Callable[[Mapping[str, object]], None]] = {
    "genomes.tsv": validate_genome_row,
    "taxonomy.tsv": validate_taxonomy_row,
    "matched_sequences.tsv": validate_matched_sequence_row,
    "matched_proteins.tsv": validate_matched_protein_row,
    "repeat_call_codon_usage.tsv": validate_repeat_call_codon_usage_row,
    "repeat_context.tsv": validate_repeat_context_row,
    "download_manifest.tsv": validate_download_manifest_row,
    "normalization_warnings.tsv": validate_normalization_warning_row,
    "accession_status.tsv": validate_accession_status_row,
    "accession_call_counts.tsv": validate_accession_call_count_row,
}


def validate_table_row(table_name: str, row: Mapping[str, object]) -> None:
    """Validate one row for a known publish-contract v2 table."""

    validator = TABLE_ROW_VALIDATORS.get(table_name)
    if validator is None:
        raise ContractError(f"Unsupported publish-contract v2 table: {table_name}")
    validator(row)


def _validate_required_fields(
    row: Mapping[str, object],
    *,
    fieldnames: Sequence[str],
    required_fields: Sequence[str],
    label: str,
) -> None:
    missing_columns = [fieldname for fieldname in fieldnames if fieldname not in row]
    if missing_columns:
        raise ContractError(f"{label} row is missing columns: {', '.join(missing_columns)}")

    empty_fields = [fieldname for fieldname in required_fields if str(row.get(fieldname, "")).strip() == ""]
    if empty_fields:
        raise ContractError(f"{label} row contains empty required fields: {', '.join(empty_fields)}")


def _parse_int(
    row: Mapping[str, object],
    *,
    fieldname: str,
    label: str,
    minimum: int | None = None,
    allow_empty: bool = False,
) -> int | None:
    value = str(row.get(fieldname, "")).strip()
    if value == "":
        if allow_empty:
            return None
        raise ContractError(f"{label} row contains an empty required field: {fieldname}")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ContractError(f"{label} row contains a non-integer {fieldname}: {value!r}") from exc
    if minimum is not None and parsed < minimum:
        raise ContractError(f"{label} row contains an out-of-range {fieldname}: {parsed}")
    return parsed


def _parse_float(
    row: Mapping[str, object],
    *,
    fieldname: str,
    label: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    value = str(row.get(fieldname, "")).strip()
    if value == "":
        raise ContractError(f"{label} row contains an empty required field: {fieldname}")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ContractError(f"{label} row contains a non-numeric {fieldname}: {value!r}") from exc
    if minimum is not None and parsed < minimum:
        raise ContractError(f"{label} row contains an out-of-range {fieldname}: {parsed}")
    if maximum is not None and parsed > maximum:
        raise ContractError(f"{label} row contains an out-of-range {fieldname}: {parsed}")
    return parsed
