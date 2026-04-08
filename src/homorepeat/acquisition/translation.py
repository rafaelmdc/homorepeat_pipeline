"""Conservative CDS translation helpers."""

from __future__ import annotations

from dataclasses import dataclass


STANDARD_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

TRANSLATION_TABLES = {
    "1": STANDARD_TABLE,
    "2": {
        **STANDARD_TABLE,
        "AGA": "*",
        "AGG": "*",
        "ATA": "M",
        "TGA": "W",
    },
    "5": {
        **STANDARD_TABLE,
        "AGA": "S",
        "AGG": "S",
        "ATA": "M",
        "TGA": "W",
    },
    "11": STANDARD_TABLE,
}
DIAGNOSTIC_TABLE_IDS = ("1", "2", "5", "11")


@dataclass(slots=True)
class TranslationResult:
    """One conservative translation attempt."""

    accepted: bool
    protein_sequence: str = ""
    translation_table: str = "1"
    warning_code: str = ""
    warning_message: str = ""


def translate_cds(sequence: str, translation_table: str | int | None) -> TranslationResult:
    """Translate a CDS conservatively under the settled Phase 2 rules."""

    table = normalize_translation_table(translation_table)
    return _translate_cds(sequence, table, enable_diagnostics=True)


def normalize_translation_table(translation_table: str | int | None) -> str:
    """Normalize a CDS translation-table identifier."""

    return str(translation_table or "1").strip() or "1"


def get_translation_table(translation_table: str | int | None) -> dict[str, str] | None:
    """Return the supported codon table for one NCBI translation-table id."""

    return TRANSLATION_TABLES.get(normalize_translation_table(translation_table))


def _translate_cds(sequence: str, table: str, *, enable_diagnostics: bool) -> TranslationResult:
    codon_table = get_translation_table(table)
    if codon_table is None:
        alternative_table = _find_supported_translation_table(sequence, skip_table=table)
        message = f"Unsupported translation table: {table}"
        if alternative_table:
            message = f"{message}; CDS translated successfully under supported table {alternative_table}"
        return TranslationResult(
            accepted=False,
            translation_table=table,
            warning_code="unsupported_translation_table",
            warning_message=message,
        )

    normalized = sequence.upper().replace("U", "T")
    if any(base not in {"A", "C", "G", "T"} for base in normalized):
        return TranslationResult(
            accepted=False,
            translation_table=table,
            warning_code="unsupported_ambiguity",
            warning_message="CDS contains unsupported ambiguous nucleotides",
        )

    if len(normalized) % 3 != 0:
        return TranslationResult(
            accepted=False,
            translation_table=table,
            warning_code="non_triplet_length",
            warning_message="CDS length is not divisible by 3",
        )

    amino_acids: list[str] = []
    stop_positions: list[int] = []
    for index in range(0, len(normalized), 3):
        codon = normalized[index : index + 3]
        amino_acid = codon_table.get(codon)
        if amino_acid is None:
            return TranslationResult(
                accepted=False,
                translation_table=table,
                warning_code="unsupported_ambiguity",
                warning_message=f"Unsupported codon encountered: {codon}",
            )
        if amino_acid == "*":
            stop_positions.append(index // 3)
        amino_acids.append(amino_acid)

    if stop_positions:
        terminal_index = len(amino_acids) - 1
        if stop_positions == [terminal_index]:
            amino_acids = amino_acids[:-1]
        else:
            result = TranslationResult(
                accepted=False,
                translation_table=table,
                warning_code="internal_stop",
                warning_message="CDS contains an internal stop codon",
            )
            if enable_diagnostics:
                alternative_table = _find_supported_translation_table(normalized, skip_table=table)
                if alternative_table:
                    return TranslationResult(
                        accepted=False,
                        translation_table=table,
                        warning_code="likely_translation_table_mismatch",
                        warning_message=(
                            f"CDS failed under translation table {table} "
                            f"but translated successfully under table {alternative_table}"
                        ),
                    )
            return result

    return TranslationResult(
        accepted=True,
        protein_sequence="".join(amino_acids),
        translation_table=table,
    )


def _find_supported_translation_table(sequence: str, *, skip_table: str) -> str:
    normalized = sequence.upper().replace("U", "T")
    for candidate in DIAGNOSTIC_TABLE_IDS:
        if candidate == skip_table:
            continue
        result = _translate_cds(normalized, candidate, enable_diagnostics=False)
        if result.accepted:
            return candidate
    return ""
