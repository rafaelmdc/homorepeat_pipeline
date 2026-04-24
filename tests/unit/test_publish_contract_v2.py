from __future__ import annotations

import unittest

from homorepeat.contracts.publish_contract_v2 import (
    DOWNLOAD_MANIFEST_FIELDNAMES,
    GENOMES_FIELDNAMES,
    MATCHED_PROTEINS_FIELDNAMES,
    MATCHED_SEQUENCES_FIELDNAMES,
    NORMALIZATION_WARNINGS_FIELDNAMES,
    REPEAT_CONTEXT_FIELDNAMES,
    TABLE_FIELDNAMES,
    validate_download_manifest_row,
    validate_matched_sequence_row,
    validate_repeat_call_codon_usage_row,
    validate_repeat_context_row,
    validate_table_row,
)
from homorepeat.io.tsv_io import ContractError


class PublishContractV2Test(unittest.TestCase):
    def test_table_registry_exposes_expected_column_order(self) -> None:
        self.assertEqual(TABLE_FIELDNAMES["genomes.tsv"], GENOMES_FIELDNAMES)
        self.assertEqual(TABLE_FIELDNAMES["matched_sequences.tsv"], MATCHED_SEQUENCES_FIELDNAMES)
        self.assertEqual(TABLE_FIELDNAMES["matched_proteins.tsv"], MATCHED_PROTEINS_FIELDNAMES)
        self.assertEqual(TABLE_FIELDNAMES["repeat_context.tsv"], REPEAT_CONTEXT_FIELDNAMES)
        self.assertEqual(TABLE_FIELDNAMES["download_manifest.tsv"], DOWNLOAD_MANIFEST_FIELDNAMES)
        self.assertEqual(TABLE_FIELDNAMES["normalization_warnings.tsv"], NORMALIZATION_WARNINGS_FIELDNAMES)

        self.assertEqual(GENOMES_FIELDNAMES[0], "batch_id")
        self.assertEqual(MATCHED_SEQUENCES_FIELDNAMES[0], "batch_id")
        self.assertEqual(MATCHED_PROTEINS_FIELDNAMES[0], "batch_id")

    def test_validate_matched_sequence_row_accepts_minimal_valid_row(self) -> None:
        row = {
            "batch_id": "batch_001",
            "sequence_id": "seq_001",
            "genome_id": "genome_001",
            "sequence_name": "tx1",
            "sequence_length": "42",
            "gene_symbol": "",
            "transcript_id": "",
            "isoform_id": "",
            "assembly_accession": "GCF_TEST_1.1",
            "taxon_id": "9606",
            "source_record_id": "",
            "protein_external_id": "",
            "translation_table": "1",
            "gene_group": "",
            "linkage_status": "",
            "partial_status": "",
        }

        validate_matched_sequence_row(row)

    def test_validate_matched_sequence_row_rejects_missing_required_field(self) -> None:
        row = {
            "batch_id": "",
            "sequence_id": "seq_001",
            "genome_id": "genome_001",
            "sequence_name": "tx1",
            "sequence_length": "42",
            "gene_symbol": "",
            "transcript_id": "",
            "isoform_id": "",
            "assembly_accession": "GCF_TEST_1.1",
            "taxon_id": "9606",
            "source_record_id": "",
            "protein_external_id": "",
            "translation_table": "1",
            "gene_group": "",
            "linkage_status": "",
            "partial_status": "",
        }

        with self.assertRaisesRegex(ContractError, "empty required fields: batch_id"):
            validate_matched_sequence_row(row)

    def test_validate_repeat_call_codon_usage_row_rejects_invalid_fraction(self) -> None:
        row = {
            "call_id": "call_001",
            "method": "pure",
            "repeat_residue": "Q",
            "sequence_id": "seq_001",
            "protein_id": "prot_001",
            "amino_acid": "Q",
            "codon": "CAA",
            "codon_count": "3",
            "codon_fraction": "1.5",
        }

        with self.assertRaisesRegex(ContractError, "out-of-range codon_fraction"):
            validate_repeat_call_codon_usage_row(row)

    def test_validate_repeat_context_row_rejects_flank_longer_than_window(self) -> None:
        row = {
            "call_id": "call_001",
            "protein_id": "prot_001",
            "sequence_id": "seq_001",
            "aa_left_flank": "AAAAA",
            "aa_right_flank": "Q",
            "nt_left_flank": "GCTGCT",
            "nt_right_flank": "CAA",
            "aa_context_window_size": "4",
            "nt_context_window_size": "9",
        }

        with self.assertRaisesRegex(ContractError, "amino-acid flank length exceeds"):
            validate_repeat_context_row(row)

    def test_validate_download_manifest_row_accepts_empty_optional_size(self) -> None:
        row = {
            "batch_id": "batch_001",
            "assembly_accession": "GCF_TEST_1.1",
            "download_status": "downloaded",
            "package_mode": "direct_zip",
            "download_path": "",
            "rehydrated_path": "",
            "checksum": "",
            "file_size_bytes": "",
            "download_started_at": "",
            "download_finished_at": "",
            "notes": "",
        }

        validate_download_manifest_row(row)

    def test_validate_table_row_rejects_unknown_table(self) -> None:
        with self.assertRaisesRegex(ContractError, "Unsupported publish-contract v2 table"):
            validate_table_row("unknown.tsv", {})


if __name__ == "__main__":
    unittest.main()
