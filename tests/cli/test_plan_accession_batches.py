from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from homorepeat.io.tsv_io import read_tsv


from tests.test_support import CLI_ENV, REPO_ROOT, cli_command


class PlanAccessionBatchesTest(unittest.TestCase):
    def test_plans_deduplicated_batch_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir_text:
            tempdir = Path(tempdir_text)
            accessions_file = tempdir / "accessions.txt"
            outdir = tempdir / "planning"
            accessions_file.write_text(
                "\n".join(
                    [
                        "# comment",
                        "GCF_000001405.40",
                        "",
                        "GCF_000001405.40",
                        "GCF_000001635.27",
                        "GCF_000005845.2",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            subprocess.run(
                [
                    *cli_command("plan_accession_batches"),
                    "--accessions-file",
                    str(accessions_file),
                    "--target-batch-size",
                    "2",
                    "--outdir",
                    str(outdir),
                ],
                check=True,
                cwd=REPO_ROOT,
                env=CLI_ENV,
            )

            self.assertEqual(
                (outdir / "selected_accessions.txt").read_text(encoding="utf-8").splitlines(),
                [
                    "GCF_000001405.40",
                    "GCF_000001635.27",
                    "GCF_000005845.2",
                ],
            )

            all_rows = read_tsv(outdir / "accession_batches.tsv")
            self.assertEqual(
                all_rows,
                [
                    {"batch_id": "batch_0001", "assembly_accession": "GCF_000001405.40"},
                    {"batch_id": "batch_0001", "assembly_accession": "GCF_000001635.27"},
                    {"batch_id": "batch_0002", "assembly_accession": "GCF_000005845.2"},
                ],
            )
            self.assertEqual(
                read_tsv(outdir / "batch_manifests" / "batch_0001.tsv"),
                all_rows[:2],
            )
            self.assertEqual(
                read_tsv(outdir / "batch_manifests" / "batch_0002.tsv"),
                all_rows[2:],
            )


if __name__ == "__main__":
    unittest.main()
