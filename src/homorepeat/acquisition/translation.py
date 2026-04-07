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

    table = str(translation_table or "1").strip() or "1"
    if table != "1":
        return TranslationResult(
            accepted=False,
            translation_table=table,
            warning_code="unknown_translation_table",
            warning_message=f"Unsupported translation table: {table}",
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
        amino_acid = STANDARD_TABLE.get(codon)
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
            return TranslationResult(
                accepted=False,
                translation_table=table,
                warning_code="internal_stop",
                warning_message="CDS contains an internal stop codon",
            )

    return TranslationResult(
        accepted=True,
        protein_sequence="".join(amino_acids),
        translation_table=table,
    )
