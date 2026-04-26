from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from homorepeat.contracts.publish_contract_v2 import REPEAT_CALL_CODON_USAGE_FIELDNAMES
from homorepeat.io.tsv_io import read_tsv, write_tsv

from tests.test_support import CLI_ENV, REPO_ROOT, cli_command


class MergeCodonUsageTablesCliTest(unittest.TestCase):
    def test_merge_codon_usage_tables_cli_merges_and_sorts_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            fragment_one = tmp / "threshold_Q_batch_0002_codon_usage.tsv"
            fragment_two = tmp / "pure_Q_batch_0001_codon_usage.tsv"
            outdir = tmp / "out"

            write_tsv(
                fragment_one,
                [
                    self._row(
                        call_id="call_b",
                        method="threshold",
                        sequence_id="seq_b",
                        protein_id="protein_b",
                        codon="CAA",
                    )
                ],
                fieldnames=REPEAT_CALL_CODON_USAGE_FIELDNAMES,
            )
            write_tsv(
                fragment_two,
                [
                    self._row(
                        call_id="call_a",
                        method="pure",
                        sequence_id="seq_a",
                        protein_id="protein_a",
                        codon="CAG",
                    )
                ],
                fieldnames=REPEAT_CALL_CODON_USAGE_FIELDNAMES,
            )

            result = subprocess.run(
                [
                    *cli_command("merge_codon_usage_tables"),
                    "--codon-usage-tsv",
                    str(fragment_one),
                    "--codon-usage-tsv",
                    str(fragment_two),
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
                    f"merge_codon_usage_tables failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            rows = read_tsv(outdir / "repeat_call_codon_usage.tsv")
            self.assertEqual([row["call_id"] for row in rows], ["call_a", "call_b"])
            self.assertEqual([row["method"] for row in rows], ["pure", "threshold"])

    def _row(
        self,
        *,
        call_id: str,
        method: str,
        sequence_id: str,
        protein_id: str,
        codon: str,
    ) -> dict[str, object]:
        return {
            "call_id": call_id,
            "method": method,
            "repeat_residue": "Q",
            "sequence_id": sequence_id,
            "protein_id": protein_id,
            "amino_acid": "Q",
            "codon": codon,
            "codon_count": 2,
            "codon_fraction": "1.0000000000",
        }


if __name__ == "__main__":
    unittest.main()
