from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path

from homorepeat.io.tsv_io import read_tsv, write_tsv


from tests.test_support import CLI_ENV, REPO_ROOT, cli_command
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "packages"


class SliceTwoAcquisitionTest(unittest.TestCase):
    def test_download_normalize_translate_and_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            planning_dir = tmp / "planning"
            batch_one_raw = tmp / "batches" / "batch_0001" / "raw"
            batch_one_norm = tmp / "batches" / "batch_0001" / "normalized"
            batch_two_raw = tmp / "batches" / "batch_0002" / "raw"
            batch_two_norm = tmp / "batches" / "batch_0002" / "normalized"
            merged_dir = tmp / "merged" / "acquisition"
            fake_bin_dir = tmp / "fake_bin"
            taxonomy_db = tmp / "taxonomy.sqlite"
            planning_dir.mkdir(parents=True, exist_ok=True)
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            taxonomy_db.write_text("", encoding="utf-8")

            selected_batches_path = planning_dir / "selected_batches.tsv"
            write_tsv(
                selected_batches_path,
                [
                    {
                        "batch_id": "batch_0001",
                        "request_id": "req_001",
                        "assembly_accession": "GCF_000001405.40",
                        "taxon_id": "9606",
                        "batch_reason": "split_large_taxon_fixed_size",
                        "resolved_name": "Homo sapiens",
                        "refseq_category": "reference genome",
                        "assembly_level": "Chromosome",
                        "annotation_status": "annotated:Updated annotation",
                    },
                    {
                        "batch_id": "batch_0001",
                        "request_id": "req_001",
                        "assembly_accession": "GCF_222222222.1",
                        "taxon_id": "9606",
                        "batch_reason": "split_large_taxon_fixed_size",
                        "resolved_name": "Homo sapiens",
                        "refseq_category": "representative genome",
                        "assembly_level": "Scaffold",
                        "annotation_status": "annotated:Full annotation",
                    },
                    {
                        "batch_id": "batch_0002",
                        "request_id": "req_004",
                        "assembly_accession": "GCF_000001635.27",
                        "taxon_id": "10090",
                        "batch_reason": "single_small_taxon_batch",
                        "resolved_name": "Mus musculus",
                        "refseq_category": "reference genome",
                        "assembly_level": "Chromosome",
                        "annotation_status": "annotated:Updated annotation",
                    },
                ],
                fieldnames=[
                    "batch_id",
                    "request_id",
                    "assembly_accession",
                    "taxon_id",
                    "batch_reason",
                    "resolved_name",
                    "refseq_category",
                    "assembly_level",
                    "annotation_status",
                ],
            )

            self._write_fake_datasets(fake_bin_dir / "datasets")
            self._write_fake_taxon_weaver(fake_bin_dir / "taxon-weaver")
            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"
            env["HOMOREPEAT_FIXTURES_ROOT"] = str(FIXTURES_ROOT)

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.download_ncbi_packages",
                    "--batch-manifest",
                    str(selected_batches_path),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(batch_one_raw),
                ],
                env=env,
            )
            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.normalize_cds",
                    "--package-dir",
                    str(batch_one_raw / "ncbi_package"),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(batch_one_norm),
                ],
                env=env,
            )
            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.translate_cds",
                    "--sequences-tsv",
                    str(batch_one_norm / "sequences.tsv"),
                    "--cds-fasta",
                    str(batch_one_norm / "cds.fna"),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(batch_one_norm),
                ],
                env=env,
            )

            batch_one_manifest = read_tsv(batch_one_raw / "download_manifest.tsv")
            self.assertEqual(len(batch_one_manifest), 2)
            self.assertEqual({row["download_status"] for row in batch_one_manifest}, {"downloaded"})

            batch_one_genomes = read_tsv(batch_one_norm / "genomes.tsv")
            batch_one_taxonomy = read_tsv(batch_one_norm / "taxonomy.tsv")
            batch_one_sequences = read_tsv(batch_one_norm / "sequences.tsv")
            batch_one_proteins = read_tsv(batch_one_norm / "proteins.tsv")
            batch_one_warnings = read_tsv(batch_one_norm / "normalization_warnings.tsv")
            batch_one_validation = json.loads((batch_one_norm / "acquisition_validation.json").read_text(encoding="utf-8"))

            self.assertEqual(len(batch_one_genomes), 2)
            self.assertEqual(len(batch_one_taxonomy), 3)
            taxonomy_by_id = {row["taxon_id"]: row for row in batch_one_taxonomy}
            self.assertEqual(taxonomy_by_id["1"]["taxon_name"], "root")
            self.assertEqual(taxonomy_by_id["1"]["parent_taxon_id"], "")
            self.assertEqual(taxonomy_by_id["9605"]["taxon_name"], "Homo")
            self.assertEqual(taxonomy_by_id["9605"]["parent_taxon_id"], "1")
            self.assertEqual(taxonomy_by_id["9606"]["taxon_name"], "Homo sapiens")
            self.assertEqual(taxonomy_by_id["9606"]["parent_taxon_id"], "9605")
            self.assertEqual(taxonomy_by_id["9606"]["rank"], "species")
            self.assertEqual(taxonomy_by_id["9606"]["source"], "taxon_weaver:2026-04-05")
            self.assertEqual(len(batch_one_sequences), 4)
            self.assertEqual(len(batch_one_proteins), 2)
            self.assertEqual(sorted(row["gene_symbol"] for row in batch_one_proteins), ["ABC1", "XYZ1"])
            self.assertEqual([row["warning_code"] for row in batch_one_warnings], ["non_triplet_length"])
            self.assertEqual(batch_one_validation["status"], "warn")

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.download_ncbi_packages",
                    "--batch-manifest",
                    str(selected_batches_path),
                    "--batch-id",
                    "batch_0002",
                    "--outdir",
                    str(batch_two_raw),
                ],
                env=env,
            )
            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.normalize_cds",
                    "--package-dir",
                    str(batch_two_raw / "ncbi_package"),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--batch-id",
                    "batch_0002",
                    "--outdir",
                    str(batch_two_norm),
                ],
                env=env,
            )
            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.translate_cds",
                    "--sequences-tsv",
                    str(batch_two_norm / "sequences.tsv"),
                    "--cds-fasta",
                    str(batch_two_norm / "cds.fna"),
                    "--batch-id",
                    "batch_0002",
                    "--outdir",
                    str(batch_two_norm),
                ],
                env=env,
            )

            batch_two_proteins = read_tsv(batch_two_norm / "proteins.tsv")
            self.assertEqual(len(batch_two_proteins), 1)
            self.assertEqual(batch_two_proteins[0]["gene_symbol"], "MOUSE1")

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.merge_acquisition_batches",
                    "--batch-inputs",
                    str(batch_one_norm),
                    "--batch-inputs",
                    str(batch_two_norm),
                    "--outdir",
                    str(merged_dir),
                ],
                env=env,
            )

            merged_genomes = read_tsv(merged_dir / "genomes.tsv")
            merged_taxonomy = read_tsv(merged_dir / "taxonomy.tsv")
            merged_sequences = read_tsv(merged_dir / "sequences.tsv")
            merged_proteins = read_tsv(merged_dir / "proteins.tsv")
            merged_warnings = read_tsv(merged_dir / "normalization_warnings.tsv")
            merged_manifest = read_tsv(merged_dir / "download_manifest.tsv")
            merged_validation = json.loads((merged_dir / "acquisition_validation.json").read_text(encoding="utf-8"))

            self.assertEqual(len(merged_genomes), 3)
            self.assertEqual(len(merged_taxonomy), 5)
            self.assertEqual(len(merged_sequences), 5)
            self.assertEqual(len(merged_proteins), 3)
            self.assertEqual(len(merged_manifest), 3)
            self.assertEqual([row["warning_code"] for row in merged_warnings], ["non_triplet_length"])
            self.assertEqual(merged_validation["scope"], "merged")
            self.assertEqual(merged_validation["status"], "warn")

    def test_normalize_deduplicates_identical_cds_records_and_keeps_distinct_variants(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            package_root = tmp / "package"
            accession = "GCF_TEST_DUP.1"
            accession_dir = package_root / "ncbi_dataset" / "data" / accession
            fake_bin_dir = tmp / "fake_bin"
            outdir = tmp / "normalized"
            taxonomy_db = tmp / "taxonomy.sqlite"
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            accession_dir.mkdir(parents=True, exist_ok=True)
            taxonomy_db.write_text("", encoding="utf-8")
            self._write_fake_taxon_weaver(fake_bin_dir / "taxon-weaver")

            (package_root / "ncbi_dataset" / "data" / "assembly_data_report.jsonl").write_text(
                json.dumps(
                    {
                        "accession": accession,
                        "assemblyInfo": {
                            "assemblyLevel": "Chromosome",
                            "assemblyType": "haploid",
                        },
                        "organism": {"taxId": 9606, "organismName": "Homo sapiens"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / f"{accession}_genomic.gff").write_text(
                "\n".join(
                    [
                        "chr1\tRefSeq\tgene\t1\t9\t.\t+\t.\tID=gene1;gene=GENE1",
                        "chr1\tRefSeq\tmRNA\t1\t9\t.\t+\t.\tID=rna1;Parent=gene1;transcript_id=NM_TEST.1;gene=GENE1",
                        "chr1\tRefSeq\tCDS\t1\t9\t.\t+\t0\tID=cds-NP_TEST.1-1;Parent=rna1;protein_id=NP_TEST.1;transcript_id=NM_TEST.1;transl_table=1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / f"{accession}_cds_from_genomic.fna").write_text(
                "\n".join(
                    [
                        ">lcl|cds1 [gene=GENE1] [protein_id=NP_TEST.1] [transcript_id=NM_TEST.1] [transl_table=1]",
                        "ATGGCCGCC",
                        ">lcl|cds2 [gene=GENE1] [protein_id=NP_TEST.1] [transcript_id=NM_TEST.1] [transl_table=1]",
                        "ATGGCCGCC",
                        ">lcl|cds3 [gene=GENE1] [protein_id=NP_TEST.1] [transcript_id=NM_TEST.1] [transl_table=1]",
                        "ATGGCCGCT",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.normalize_cds",
                    "--package-dir",
                    str(package_root),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(outdir),
                ],
                env=env,
            )

            sequences = read_tsv(outdir / "sequences.tsv")
            warnings_rows = read_tsv(outdir / "normalization_warnings.tsv")
            cds_records = read_tsv(outdir / "genomes.tsv")

            self.assertEqual(len(cds_records), 1)
            self.assertEqual(len(sequences), 2)
            self.assertEqual(len({row["sequence_id"] for row in sequences}), 2)
            self.assertEqual(
                [row["warning_code"] for row in warnings_rows],
                ["conflicting_duplicate_cds_key"],
            )
            self.assertEqual((outdir / "cds.fna").read_text(encoding="utf-8").count(">"), 2)

    def test_normalize_filters_alt_loci_using_sequence_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            package_root = tmp / "package"
            accession = "GCF_TEST_PRIMARY.1"
            accession_dir = package_root / "ncbi_dataset" / "data" / accession
            fake_bin_dir = tmp / "fake_bin"
            outdir = tmp / "normalized"
            taxonomy_db = tmp / "taxonomy.sqlite"
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            accession_dir.mkdir(parents=True, exist_ok=True)
            taxonomy_db.write_text("", encoding="utf-8")
            self._write_fake_taxon_weaver(fake_bin_dir / "taxon-weaver")

            (package_root / "ncbi_dataset" / "data" / "assembly_data_report.jsonl").write_text(
                json.dumps(
                    {
                        "accession": accession,
                        "assemblyInfo": {
                            "assemblyLevel": "Chromosome",
                            "assemblyType": "haploid",
                        },
                        "organism": {"taxId": 9606, "organismName": "Homo sapiens"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / "sequence_report.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "assemblyAccession": accession,
                                "assemblyUnit": "Primary Assembly",
                                "refseqAccession": "NC_000001.11",
                                "role": "assembled-molecule",
                            }
                        ),
                        json.dumps(
                            {
                                "assemblyAccession": accession,
                                "assemblyUnit": "ALT_REF_LOCI_1",
                                "refseqAccession": "NT_187515.1",
                                "role": "alt-scaffold",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / f"{accession}_genomic.gff").write_text(
                "\n".join(
                    [
                        "NC_000001.11\tRefSeq\tgene\t1\t9\t.\t+\t.\tID=gene1;gene=GENE1",
                        "NC_000001.11\tRefSeq\tmRNA\t1\t9\t.\t+\t.\tID=rna-NM_MAIN.1;Parent=gene1;transcript_id=NM_MAIN.1;gene=GENE1",
                        "NC_000001.11\tRefSeq\tCDS\t1\t9\t.\t+\t0\tID=cds-NP_MAIN.1;Parent=rna-NM_MAIN.1;protein_id=NP_MAIN.1;gene=GENE1;gbkey=CDS",
                        "NT_187515.1\tRefSeq\tgene\t1\t9\t.\t+\t.\tID=gene2;gene=GENE2",
                        "NT_187515.1\tRefSeq\tmRNA\t1\t9\t.\t+\t.\tID=rna-NM_ALT.1;Parent=gene2;transcript_id=NM_ALT.1;gene=GENE2",
                        "NT_187515.1\tRefSeq\tCDS\t1\t9\t.\t+\t0\tID=cds-NP_ALT.1;Parent=rna-NM_ALT.1;protein_id=NP_ALT.1;gene=GENE2;gbkey=CDS",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / f"{accession}_cds_from_genomic.fna").write_text(
                "\n".join(
                    [
                        ">lcl|NC_000001.11_cds_NP_MAIN.1_1 [gene=GENE1] [protein=main protein [primary]] [protein_id=NP_MAIN.1] [gbkey=CDS]",
                        "ATGGCCGCC",
                        ">lcl|NT_187515.1_cds_NP_ALT.1_2 [gene=GENE2] [protein=alt protein [alt]] [protein_id=NP_ALT.1] [gbkey=CDS]",
                        "ATGAAAGCC",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.normalize_cds",
                    "--package-dir",
                    str(package_root),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(outdir),
                ],
                env=env,
            )

            sequences = read_tsv(outdir / "sequences.tsv")
            warnings_rows = read_tsv(outdir / "normalization_warnings.tsv")

            self.assertEqual(len(sequences), 1)
            self.assertEqual(sequences[0]["gene_symbol"], "GENE1")
            self.assertEqual(sequences[0]["protein_external_id"], "NP_MAIN.1")
            self.assertEqual(sequences[0]["linkage_status"], "gff")
            self.assertEqual(warnings_rows, [])
            self.assertEqual((outdir / "cds.fna").read_text(encoding="utf-8").count(">"), 1)

    def _run_cli(self, command: list[str], *, env: dict[str, str]) -> None:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env={**CLI_ENV, **env},
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                f"Command failed with exit code {result.returncode}: {' '.join(command)}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

    def _write_fake_datasets(self, path: Path) -> None:
        script = textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import os
            import pathlib
            import shutil
            import sys
            import zipfile

            def zip_tree(source_root: pathlib.Path, destination_zip: pathlib.Path) -> None:
                destination_zip.parent.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(destination_zip, "w") as archive:
                    for file_path in sorted(source_root.rglob("*")):
                        if file_path.is_file():
                            archive.write(file_path, file_path.relative_to(source_root))

            args = sys.argv[1:]
            fixtures_root = pathlib.Path(os.environ["HOMOREPEAT_FIXTURES_ROOT"])

            if args[:3] == ["download", "genome", "accession"]:
                inputfile = pathlib.Path(args[args.index("--inputfile") + 1])
                filename = pathlib.Path(args[args.index("--filename") + 1])
                accessions = {line.strip() for line in inputfile.read_text(encoding="utf-8").splitlines() if line.strip()}
                if accessions == {"GCF_000001405.40", "GCF_222222222.1"}:
                    zip_tree(fixtures_root / "batch_a", filename)
                    raise SystemExit(0)
                if accessions == {"GCF_000001635.27"}:
                    zip_tree(fixtures_root / "batch_b", filename)
                    raise SystemExit(0)
                raise SystemExit(1)

            if args[:1] == ["rehydrate"]:
                raise SystemExit(0)

            raise SystemExit(1)
            """
        )
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def _write_fake_taxon_weaver(self, path: Path) -> None:
        script = textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import sys

            args = sys.argv[1:]
            if args[:1] == ["build-info"]:
                print(json.dumps({"taxonomy_build_version": "2026-04-05"}))
                raise SystemExit(0)

            if args[:1] == ["inspect-lineage"]:
                taxid = args[args.index("--taxid") + 1]
                if taxid == "9606":
                    print(json.dumps({
                        "taxid": 9606,
                        "lineage": [
                            {"taxid": 1, "rank": "no rank", "name": "root"},
                            {"taxid": 9605, "rank": "genus", "name": "Homo"},
                            {"taxid": 9606, "rank": "species", "name": "Homo sapiens"},
                        ],
                    }))
                    raise SystemExit(0)
                if taxid == "10090":
                    print(json.dumps({
                        "taxid": 10090,
                        "lineage": [
                            {"taxid": 1, "rank": "no rank", "name": "root"},
                            {"taxid": 10088, "rank": "genus", "name": "Mus"},
                            {"taxid": 10090, "rank": "species", "name": "Mus musculus"},
                        ],
                    }))
                    raise SystemExit(0)
                raise SystemExit(1)

            raise SystemExit(1)
            """
        )
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


if __name__ == "__main__":
    unittest.main()
