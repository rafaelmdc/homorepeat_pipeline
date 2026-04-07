from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from homorepeat.io.fasta_io import extract_ncbi_molecule_accession, parse_ncbi_fasta_header
from homorepeat.acquisition.gff_norm import build_gff_index, resolve_linkage
from homorepeat.core.ids import stable_id
from homorepeat.acquisition.ncbi_datasets import project_assembly_record
from homorepeat.io.tsv_io import read_tsv, write_tsv
from homorepeat.contracts.warnings import build_warning_row


from tests.test_support import CLI_ENV, REPO_ROOT, cli_command


class SliceZeroHelpersTest(unittest.TestCase):
    def test_stable_id_is_deterministic(self) -> None:
        left = stable_id("genome", "GCF_000001405.40", 9606)
        right = stable_id("genome", "GCF_000001405.40", 9606)
        self.assertEqual(left, right)
        self.assertTrue(left.startswith("genome_"))

    def test_tsv_round_trip_preserves_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "example.tsv"
            fieldnames = ["request_id", "input_value", "input_type"]
            rows = [
                {
                    "request_id": "req_001",
                    "input_value": "Homo sapiens",
                    "input_type": "scientific_name",
                }
            ]
            write_tsv(path, rows, fieldnames=fieldnames)
            loaded = read_tsv(path, required_columns=fieldnames)
            self.assertEqual(loaded, rows)

    def test_warning_helper_shapes_canonical_row(self) -> None:
        row = build_warning_row(
            "partial_cds",
            "sequence",
            "Partial CDS cannot be translated conservatively",
            sequence_id="seq_001",
        )
        self.assertEqual(row["warning_code"], "partial_cds")
        self.assertEqual(row["warning_scope"], "sequence")
        self.assertEqual(row["sequence_id"], "seq_001")
        self.assertEqual(row["protein_id"], "")

    def test_project_assembly_record_accepts_snake_case_datasets_payload(self) -> None:
        row = project_assembly_record(
            {
                "request_id": "req_001",
                "matched_taxid": "9606",
                "matched_name": "Homo sapiens",
                "input_type": "assembly_accession",
            },
            {
                "accession": "GCF_000001405.40",
                "current_accession": "GCF_000001405.40",
                "source_database": "SOURCE_DATABASE_REFSEQ",
                "assembly_info": {
                    "assembly_level": "Chromosome",
                    "assembly_type": "haploid-with-alt-loci",
                    "assembly_status": "current",
                    "refseq_category": "reference genome",
                },
                "annotation_info": {"status": "Updated annotation"},
                "organism": {"tax_id": 9606, "organism_name": "Homo sapiens"},
            },
        )
        self.assertEqual(row["source_database"], "REFSEQ")
        self.assertEqual(row["assembly_status"], "current")
        self.assertEqual(row["annotation_status"], "annotated:Updated annotation")
        self.assertEqual(row["organism_name"], "Homo sapiens")
        self.assertEqual(row["taxid"], "9606")

    def test_parse_ncbi_fasta_header_handles_nested_brackets(self) -> None:
        header = (
            "lcl|NC_000001.11_cds_NP_001394290.1_1456 "
            "[gene=SDHB] "
            "[protein=succinate dehydrogenase [ubiquinone] iron-sulfur subunit, mitochondrial isoform 2] "
            "[protein_id=NP_001394290.1] "
            "[gbkey=CDS]"
        )
        metadata = parse_ncbi_fasta_header(header)
        self.assertEqual(metadata["record_id"], "NC_000001.11_cds_NP_001394290.1_1456")
        self.assertEqual(metadata["protein_id"], "NP_001394290.1")
        self.assertEqual(
            metadata["protein"],
            "succinate dehydrogenase [ubiquinone] iron-sulfur subunit, mitochondrial isoform 2",
        )
        self.assertEqual(
            extract_ncbi_molecule_accession(metadata["record_id"]),
            "NC_000001.11",
        )

    def test_resolve_linkage_handles_gene_segment_cds_without_protein_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gff_path = Path(tmpdir) / "segment.gff"
            gff_path.write_text(
                "\n".join(
                    [
                        "NC_000002.12\tCurated Genomic\tgene\t1\t100\t.\t-\t.\tID=gene-IGKC;gene=IGKC",
                        "NC_000002.12\tCurated Genomic\tC_gene_segment\t1\t100\t.\t-\t.\tID=id-IGKC;Parent=gene-IGKC;gene=IGKC;standard_name=IGKC",
                        "NC_000002.12\tCurated Genomic\tCDS\t1\t100\t.\t-\t2\tID=cds-IGKC;Parent=id-IGKC;gene=IGKC;partial=true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            metadata = parse_ncbi_fasta_header(
                "lcl|NC_000002.12_cds_16040 "
                "[gene=IGKC] "
                "[frame=3] "
                "[partial=5'] "
                "[exception=rearrangement required for product] "
                "[location=complement(88857361..>88857683)] "
                "[gbkey=CDS]"
            )
            linkage = resolve_linkage(metadata, build_gff_index(gff_path))
            self.assertIsNotNone(linkage)
            assert linkage is not None
            self.assertEqual(linkage.gene_symbol, "IGKC")
            self.assertEqual(linkage.source_record_id, "cds-IGKC")
            self.assertEqual(linkage.match_source, "gff_gene_segment_alias")


class SliceOneCliTest(unittest.TestCase):
    def test_request_resolution_and_planning_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            planning_dir = tmp / "planning"
            fake_bin_dir = tmp / "fake_bin"
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            requested_taxa = planning_dir / "requested_taxa.tsv"
            planning_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(
                REPO_ROOT / "tests" / "fixtures" / "requests" / "requested_taxa.tsv",
                requested_taxa,
            )

            taxonomy_db = tmp / "taxonomy.sqlite"
            taxonomy_db.write_text("", encoding="utf-8")
            self._write_fake_taxon_weaver(fake_bin_dir / "taxon-weaver")
            self._write_fake_datasets(fake_bin_dir / "datasets")

            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.resolve_taxa",
                    "--requested-taxa",
                    str(requested_taxa),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--outdir",
                    str(planning_dir),
                ],
                env=env,
            )
            resolved_rows = read_tsv(planning_dir / "resolved_requests.tsv")
            review_rows = read_tsv(planning_dir / "taxonomy_review_queue.tsv")
            self.assertEqual(len(resolved_rows), 3)
            self.assertEqual(len(review_rows), 1)
            self.assertEqual(review_rows[0]["request_id"], "req_002")
            self.assertEqual(review_rows[0]["resolution_status"], "review_required")

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.enumerate_assemblies",
                    "--resolved-requests",
                    str(planning_dir / "resolved_requests.tsv"),
                    "--outdir",
                    str(planning_dir),
                    "--include-raw-jsonl",
                ],
                env=env,
            )
            inventory_rows = read_tsv(planning_dir / "assembly_inventory.tsv")
            self.assertEqual(len(inventory_rows), 6)
            self.assertTrue((planning_dir / "assembly_inventory.jsonl").is_file())

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.select_assemblies",
                    "--assembly-inventory",
                    str(planning_dir / "assembly_inventory.tsv"),
                    "--outdir",
                    str(planning_dir),
                ],
                env=env,
            )
            selected_rows = read_tsv(planning_dir / "selected_assemblies.tsv")
            excluded_rows = read_tsv(planning_dir / "excluded_assemblies.tsv")
            self.assertEqual(len(selected_rows), 2)
            self.assertEqual(len(excluded_rows), 4)
            self.assertEqual(
                {row["selection_reason"] for row in selected_rows},
                {
                    "selected_refseq_reference_annotated",
                    "selected_refseq_representative_annotated",
                },
            )

            selected_accessions = (
                planning_dir / "selected_accessions.txt"
            ).read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(
                selected_accessions,
                ["GCF_000001405.40", "GCF_123456789.1"],
            )

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.plan_batches",
                    "--selected-assemblies",
                    str(planning_dir / "selected_assemblies.tsv"),
                    "--outdir",
                    str(planning_dir),
                    "--target-batch-size",
                    "1",
                ],
                env=env,
            )
            batch_rows = read_tsv(planning_dir / "selected_batches.tsv")
            self.assertEqual(len(batch_rows), 2)
            self.assertEqual({row["batch_id"] for row in batch_rows}, {"batch_0001", "batch_0002"})
            self.assertEqual(
                {row["batch_reason"] for row in batch_rows},
                {"split_large_taxon_fixed_size"},
            )

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

    def _write_fake_taxon_weaver(self, path: Path) -> None:
        script = textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import sys

            command = sys.argv[1]
            if command == "build-info":
                print(json.dumps({"taxonomy_build_version": "2026-04-05"}))
                raise SystemExit(0)

            if command == "inspect-lineage":
                print(json.dumps({
                    "taxid": 9606,
                    "lineage": [
                        {"taxid": 1, "rank": "no rank", "name": "root"},
                        {"taxid": 9605, "rank": "genus", "name": "Homo"},
                        {"taxid": 9606, "rank": "species", "name": "Homo sapiens"},
                    ],
                }))
                raise SystemExit(0)

            if command == "resolve-name":
                name = sys.argv[2]
                if name == "Homo sapiens":
                    print(json.dumps({
                        "normalized_name": "Homo sapiens",
                        "status": "resolved_exact_scientific",
                        "review_required": False,
                        "matched_taxid": 9606,
                        "matched_name": "Homo sapiens",
                        "matched_rank": "species",
                        "warnings": [],
                        "taxonomy_build_version": "2026-04-05",
                        "lineage": [
                            {"taxid": 1, "rank": "no rank", "name": "root"},
                            {"taxid": 9605, "rank": "genus", "name": "Homo"},
                            {"taxid": 9606, "rank": "species", "name": "Homo sapiens"},
                        ],
                    }))
                    raise SystemExit(0)
                if name == "bass":
                    print(json.dumps({
                        "normalized_name": "bass",
                        "status": "ambiguous_fuzzy_multiple",
                        "review_required": True,
                        "matched_taxid": None,
                        "matched_name": None,
                        "matched_rank": None,
                        "warnings": ["ambiguous common-name resolution"],
                        "taxonomy_build_version": "2026-04-05",
                        "lineage": [],
                    }))
                    raise SystemExit(0)
                raise SystemExit(1)

            raise SystemExit(1)
            """
        )
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def _write_fake_datasets(self, path: Path) -> None:
        script = textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import sys

            records = {
                "9606": [
                    {
                        "accession": "GCF_000001405.40",
                        "currentAccession": "GCF_000001405.40",
                        "sourceDatabase": "SOURCE_DATABASE_REFSEQ",
                        "assemblyInfo": {
                            "assemblyLevel": "Chromosome",
                            "assemblyType": "haploid",
                            "assemblyStatus": "current",
                            "refseqCategory": "reference genome"
                        },
                        "annotationInfo": {"status": "Updated annotation"},
                        "organism": {"taxId": 9606, "organismName": "Homo sapiens"}
                    },
                    {
                        "accession": "GCF_123456789.1",
                        "currentAccession": "GCF_123456789.1",
                        "sourceDatabase": "SOURCE_DATABASE_REFSEQ",
                        "assemblyInfo": {
                            "assemblyLevel": "Scaffold",
                            "assemblyType": "haploid",
                            "assemblyStatus": "current",
                            "refseqCategory": "representative genome"
                        },
                        "annotationInfo": {"status": "Full annotation"},
                        "organism": {"taxId": 9606, "organismName": "Homo sapiens"}
                    },
                    {
                        "accession": "GCF_555555555.1",
                        "currentAccession": "GCF_555555555.1",
                        "sourceDatabase": "SOURCE_DATABASE_REFSEQ",
                        "assemblyInfo": {
                            "assemblyLevel": "Scaffold",
                            "assemblyType": "haploid",
                            "assemblyStatus": "current",
                            "refseqCategory": ""
                        },
                        "organism": {"taxId": 9606, "organismName": "Homo sapiens"}
                    }
                ],
                "GCF_000001405.40": [
                    {
                        "accession": "GCF_000001405.40",
                        "currentAccession": "GCF_000001405.40",
                        "sourceDatabase": "SOURCE_DATABASE_REFSEQ",
                        "assemblyInfo": {
                            "assemblyLevel": "Chromosome",
                            "assemblyType": "haploid",
                            "assemblyStatus": "current",
                            "refseqCategory": "reference genome"
                        },
                        "annotationInfo": {"status": "Updated annotation"},
                        "organism": {"taxId": 9606, "organismName": "Homo sapiens"}
                    }
                ],
            }

            args = sys.argv[1:]
            if args[:3] != ["summary", "genome", "taxon"] and args[:3] != ["summary", "genome", "accession"]:
                raise SystemExit(1)
            query = args[3]
            for record in records.get(query, []):
                print(json.dumps(record))
            raise SystemExit(0)
            """
        )
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


if __name__ == "__main__":
    unittest.main()
