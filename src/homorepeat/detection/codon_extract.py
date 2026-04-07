"""Conservative codon-slicing helpers for finalized amino-acid calls."""

from __future__ import annotations

from dataclasses import dataclass

from homorepeat.acquisition.translation import translate_cds


@dataclass(slots=True)
class CodonSliceResult:
    """One codon-slicing attempt for a finalized amino-acid call."""

    accepted: bool
    codon_sequence: str = ""
    warning_message: str = ""


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
