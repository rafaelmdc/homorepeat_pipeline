from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from homorepeat.contracts.repeat_features import CALL_FIELDNAMES, build_call_row
from homorepeat.io.fasta_io import write_fasta
from homorepeat.io.tsv_io import read_tsv, write_tsv

from tests.test_support import CLI_ENV, REPO_ROOT, cli_command


class ExportRepeatContextCliTest(unittest.TestCase):
    def test_export_repeat_context_cli_extracts_boundary_flanks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            batch_dir = tmp / "batch_0001"
            outdir = tmp / "out"
            batch_dir.mkdir(parents=True, exist_ok=True)
            calls_tsv = tmp / "repeat_calls.tsv"

            call_row = build_call_row(
                method="pure",
                genome_id="genome_1",
                taxon_id="9606",
                sequence_id="seq_1",
                protein_id="protein_1",
                repeat_residue="Q",
                start=3,
                end=5,
                aa_sequence="QQQ",
            )
            write_tsv(calls_tsv, [call_row], fieldnames=CALL_FIELDNAMES)
            write_fasta(batch_dir / "proteins.faa", [("protein_1", "AAQQQGG")])
            write_fasta(batch_dir / "cds.fna", [("seq_1", "GCTGCTCAACAGCAAGGTGGT")])

            result = subprocess.run(
                [
                    *cli_command("export_repeat_context"),
                    "--repeat-calls-tsv",
                    str(calls_tsv),
                    "--batch-dir",
                    str(batch_dir),
                    "--aa-context-window-size",
                    "2",
                    "--nt-context-window-size",
                    "6",
                    "--outdir",
                    str(outdir),
                ],
                cwd=REPO_ROOT,
                env=CLI_ENV,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.fail(
                    f"export_repeat_context failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            rows = read_tsv(outdir / "repeat_context.tsv")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["call_id"], call_row["call_id"])
            self.assertEqual(rows[0]["aa_left_flank"], "AA")
            self.assertEqual(rows[0]["aa_right_flank"], "GG")
            self.assertEqual(rows[0]["nt_left_flank"], "GCTGCT")
            self.assertEqual(rows[0]["nt_right_flank"], "GGTGGT")


if __name__ == "__main__":
    unittest.main()
