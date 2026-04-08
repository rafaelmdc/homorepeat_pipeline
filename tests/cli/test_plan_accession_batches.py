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
                    "--no-resolve-accessions",
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

    def test_resolves_genbank_inputs_to_paired_refseq_before_batching(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir_text:
            tempdir = Path(tempdir_text)
            accessions_file = tempdir / "accessions.txt"
            outdir = tempdir / "planning"
            fake_bin_dir = tempdir / "fake_bin"
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            accessions_file.write_text(
                "\n".join(
                    [
                        "GCA_032362555.1",
                        "GCF_000001405.40",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            datasets_bin = fake_bin_dir / "datasets"
            datasets_bin.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env python3",
                        "import json",
                        "import sys",
                        "args = sys.argv[1:]",
                        "if args[:3] != ['summary', 'genome', 'accession'] or '--as-json-lines' not in args:",
                        "    raise SystemExit(2)",
                        "accession = args[3]",
                        "records = {",
                        "    'GCA_032362555.1': {",
                        "        'accession': 'GCA_032362555.1',",
                        "        'currentAccession': 'GCA_032362555.1',",
                        "        'pairedAccession': 'GCF_032362555.1',",
                        "        'sourceDatabase': 'SOURCE_DATABASE_GENBANK',",
                        "        'assemblyInfo': {",
                        "            'pairedAssembly': {",
                        "                'status': 'current',",
                        "                'annotationName': 'GCF_032362555.1-RS_2023_11'",
                        "            }",
                        "        },",
                        "        'annotationInfo': {}",
                        "    },",
                        "    'GCF_000001405.40': {",
                        "        'accession': 'GCF_000001405.40',",
                        "        'currentAccession': 'GCF_000001405.40',",
                        "        'sourceDatabase': 'SOURCE_DATABASE_REFSEQ',",
                        "        'annotationInfo': {",
                        "            'status': 'annotated'",
                        "        }",
                        "    }",
                        "}",
                        "record = records.get(accession)",
                        "if record is None:",
                        "    raise SystemExit(3)",
                        "print(json.dumps(record))",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            datasets_bin.chmod(0o755)

            env = dict(CLI_ENV)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"

            subprocess.run(
                [
                    *cli_command("plan_accession_batches"),
                    "--accessions-file",
                    str(accessions_file),
                    "--datasets-bin",
                    "datasets",
                    "--target-batch-size",
                    "10",
                    "--outdir",
                    str(outdir),
                ],
                check=True,
                cwd=REPO_ROOT,
                env=env,
            )

            self.assertEqual(
                (outdir / "selected_accessions.txt").read_text(encoding="utf-8").splitlines(),
                [
                    "GCF_032362555.1",
                    "GCF_000001405.40",
                ],
            )
            self.assertEqual(
                read_tsv(outdir / "accession_resolution.tsv"),
                [
                    {
                        "requested_accession": "GCA_032362555.1",
                        "resolved_accession": "GCF_032362555.1",
                        "resolution_reason": "resolved_genbank_to_paired_refseq_annotated",
                        "source_database": "GENBANK",
                        "current_accession": "GCA_032362555.1",
                        "paired_accession": "GCF_032362555.1",
                        "annotation_status": "not_annotated",
                    },
                    {
                        "requested_accession": "GCF_000001405.40",
                        "resolved_accession": "GCF_000001405.40",
                        "resolution_reason": "kept_requested_accession",
                        "source_database": "REFSEQ",
                        "current_accession": "GCF_000001405.40",
                        "paired_accession": "",
                        "annotation_status": "annotated:annotated",
                    },
                ],
            )
            self.assertEqual(
                read_tsv(outdir / "accession_batches.tsv"),
                [
                    {"batch_id": "batch_0001", "assembly_accession": "GCF_032362555.1"},
                    {"batch_id": "batch_0001", "assembly_accession": "GCF_000001405.40"},
                ],
            )


if __name__ == "__main__":
    unittest.main()
