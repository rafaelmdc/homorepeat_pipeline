"""Conservative codon-slicing helpers for finalized amino-acid calls."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from homorepeat.acquisition.translation import STANDARD_TABLE, translate_cds


@dataclass(slots=True)
class CodonSliceResult:
    """One codon-slicing attempt for a finalized amino-acid call."""

    accepted: bool
    codon_sequence: str = ""
    warning_message: str = ""


CODON_USAGE_FIELDNAMES = [
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


def extract_call_codons(
    cds_sequence: str,
    *,
    aa_start: int,
    aa_end: int,
    aa_sequence: str,
    translation_table: str | int | None,
) -> CodonSliceResult:
    """Slice one codon tract from a CDS using 1-based amino-acid coordinates."""

    if aa_start < 1 or aa_end < aa_start:
        return CodonSliceResult(accepted=False, warning_message="invalid amino-acid coordinates")

    normalized_aa_sequence = aa_sequence.strip().upper()
    expected_length = aa_end - aa_start + 1
    if len(normalized_aa_sequence) != expected_length:
        return CodonSliceResult(
            accepted=False,
            warning_message="amino-acid tract length does not match coordinates",
        )

    normalized_cds = cds_sequence.strip().upper().replace("U", "T")
    nt_start = (aa_start - 1) * 3
    nt_end = aa_end * 3
    if nt_end > len(normalized_cds):
        return CodonSliceResult(
            accepted=False,
            warning_message="codon slice exceeds CDS length",
        )

    codon_sequence = normalized_cds[nt_start:nt_end]
    if len(codon_sequence) != expected_length * 3:
        return CodonSliceResult(
            accepted=False,
            warning_message="codon slice length does not equal 3 * tract length",
        )

    translation_result = translate_cds(codon_sequence, translation_table)
    if not translation_result.accepted:
        warning_message = translation_result.warning_message or "codon slice translation failed"
        return CodonSliceResult(accepted=False, warning_message=warning_message)

    if translation_result.protein_sequence != normalized_aa_sequence:
        return CodonSliceResult(
            accepted=False,
            warning_message="codon slice translation does not match amino-acid tract",
        )

    return CodonSliceResult(
        accepted=True,
        codon_sequence=codon_sequence,
    )


def build_codon_usage_rows(
    call_row: dict[str, str],
    *,
    translation_table: str | int | None,
) -> list[dict[str, object]]:
    """Build normalized codon-usage rows for one finalized call with a validated codon sequence."""

    table = str(translation_table or "1").strip() or "1"
    if table != "1":
        raise ValueError(f"Unsupported translation table: {table}")

    codon_sequence = str(call_row.get("codon_sequence", "")).strip().upper().replace("U", "T")
    if not codon_sequence:
        return []
    if len(codon_sequence) % 3 != 0:
        raise ValueError("codon_sequence length is not divisible by 3")

    codons = [codon_sequence[index : index + 3] for index in range(0, len(codon_sequence), 3)]
    amino_acids: list[str] = []
    for codon in codons:
        amino_acid = STANDARD_TABLE.get(codon)
        if amino_acid is None or amino_acid == "*":
            raise ValueError(f"Unsupported codon encountered in codon_sequence: {codon}")
        amino_acids.append(amino_acid)

    aa_sequence = str(call_row.get("aa_sequence", "")).strip().upper()
    if "".join(amino_acids) != aa_sequence:
        raise ValueError("codon_sequence does not translate to the call amino-acid tract")

    counts_by_amino_acid: dict[str, Counter[str]] = {}
    for amino_acid, codon in zip(amino_acids, codons, strict=True):
        counts_by_amino_acid.setdefault(amino_acid, Counter())[codon] += 1

    rows: list[dict[str, object]] = []
    for amino_acid in sorted(counts_by_amino_acid):
        codon_counts = counts_by_amino_acid[amino_acid]
        amino_acid_total = sum(codon_counts.values())
        for codon in sorted(codon_counts):
            codon_count = codon_counts[codon]
            rows.append(
                {
                    "call_id": call_row.get("call_id", ""),
                    "method": call_row.get("method", ""),
                    "repeat_residue": call_row.get("repeat_residue", ""),
                    "sequence_id": call_row.get("sequence_id", ""),
                    "protein_id": call_row.get("protein_id", ""),
                    "amino_acid": amino_acid,
                    "codon": codon,
                    "codon_count": codon_count,
                    "codon_fraction": f"{codon_count / amino_acid_total:.10f}",
                }
            )
    return rows
