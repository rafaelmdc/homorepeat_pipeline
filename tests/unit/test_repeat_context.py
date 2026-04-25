from __future__ import annotations

import unittest

from homorepeat.contracts.repeat_features import build_call_row
from homorepeat.detection.repeat_context import build_repeat_context_row


class RepeatContextTest(unittest.TestCase):
    def test_build_repeat_context_row_extracts_bounded_flanks(self) -> None:
        call_row = build_call_row(
            method="pure",
            genome_id="genome_1",
            taxon_id="9606",
            sequence_id="seq_1",
            protein_id="protein_1",
            repeat_residue="Q",
            start=4,
            end=6,
            aa_sequence="QQQ",
        )

        row = build_repeat_context_row(
            call_row,
            protein_sequence="MNAQQQRST",
            cds_sequence="ATGAACGCTCAACAGCAAAGATCAACA",
            aa_context_window_size=3,
            nt_context_window_size=9,
        )

        self.assertEqual(row["aa_left_flank"], "MNA")
        self.assertEqual(row["aa_right_flank"], "RST")
        self.assertEqual(row["nt_left_flank"], "ATGAACGCT")
        self.assertEqual(row["nt_right_flank"], "AGATCAACA")

    def test_build_repeat_context_row_clips_at_sequence_edges(self) -> None:
        call_row = build_call_row(
            method="pure",
            genome_id="genome_1",
            taxon_id="9606",
            sequence_id="seq_1",
            protein_id="protein_1",
            repeat_residue="M",
            start=1,
            end=1,
            aa_sequence="M",
        )

        row = build_repeat_context_row(
            call_row,
            protein_sequence="MQQ",
            cds_sequence="ATGCAACAA",
            aa_context_window_size=5,
            nt_context_window_size=15,
        )

        self.assertEqual(row["aa_left_flank"], "")
        self.assertEqual(row["aa_right_flank"], "QQ")
        self.assertEqual(row["nt_left_flank"], "")
        self.assertEqual(row["nt_right_flank"], "CAACAA")


if __name__ == "__main__":
    unittest.main()
