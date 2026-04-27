from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from homorepeat.io.tsv_io import read_tsv
from tests.test_support import CLI_ENV, REPO_ROOT


FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "packages"
BLANK_DAG_NODE_PATTERN = re.compile(r'v[0-9]+\[" "\]|v[0-9]+\(\( \)\)')
MAX_EXPECTED_BLANK_DAG_NODES = 44


class WorkflowPublishModesTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_successful_default_raw_run_publishes_v2_flat_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_root = tmp / "run_raw"

            self._run_pipeline(
                run_root=run_root,
                accessions=["GCF_000001405.40", "GCF_000001635.27"],
            )

            publish_root = run_root / "publish"
            manifest = json.loads((publish_root / "metadata" / "run_manifest.json").read_text(encoding="utf-8"))
            launch = json.loads((publish_root / "metadata" / "launch_metadata.json").read_text(encoding="utf-8"))

            self.assertEqual(manifest["status"], "success")
            self.assertEqual(manifest["publish_contract_version"], 2)
            self.assertEqual(launch["publish_contract_version"], 2)
            self.assertEqual(manifest["acquisition_publish_mode"], "raw")
            self.assertEqual(launch["acquisition_publish_mode"], "raw")
            self.assertEqual(manifest["artifacts"]["acquisition"], {})
            self.assertEqual(manifest["artifacts"]["status"], {})
            self.assertEqual(manifest["artifacts"]["tables"]["genomes_tsv"], "publish/tables/genomes.tsv")
            self.assertEqual(
                manifest["artifacts"]["tables"]["repeat_call_codon_usage_tsv"],
                "publish/tables/repeat_call_codon_usage.tsv",
            )
            self.assertEqual(manifest["artifacts"]["tables"]["repeat_context_tsv"], "publish/tables/repeat_context.tsv")
            self.assertEqual(manifest["artifacts"]["summaries"]["status_summary_json"], "publish/summaries/status_summary.json")
            self.assertEqual(manifest["params"]["params_file_values"], {})
            self.assertEqual(manifest["params"]["effective_values"]["batch_size"], 1)
            self.assertFalse((publish_root / ".nf_placeholders").exists())

            self.assertFalse((publish_root / "acquisition").exists())
            self.assertFalse((publish_root / "status").exists())
            self.assertFalse((publish_root / "calls" / "finalized").exists())
            self.assertFalse(list(publish_root.rglob("cds.fna")))
            self.assertFalse(list(publish_root.rglob("proteins.faa")))
            self.assertTrue((publish_root / "calls" / "repeat_calls.tsv").is_file())
            self.assertTrue((publish_root / "calls" / "run_params.tsv").is_file())
            for filename in [
                "genomes.tsv",
                "taxonomy.tsv",
                "matched_sequences.tsv",
                "matched_proteins.tsv",
                "repeat_call_codon_usage.tsv",
                "repeat_context.tsv",
                "download_manifest.tsv",
                "normalization_warnings.tsv",
                "accession_status.tsv",
                "accession_call_counts.tsv",
            ]:
                self.assertTrue((publish_root / "tables" / filename).is_file(), publish_root / "tables" / filename)
            self.assertTrue((publish_root / "summaries" / "status_summary.json").is_file())
            self.assertTrue((publish_root / "summaries" / "acquisition_validation.json").is_file())
            call_sequence_ids = {
                row["sequence_id"]
                for row in read_tsv(publish_root / "calls" / "repeat_calls.tsv")
                if row.get("sequence_id", "")
            }
            matched_sequence_ids = {
                row["sequence_id"]
                for row in read_tsv(publish_root / "tables" / "matched_sequences.tsv")
                if row.get("sequence_id", "")
            }
            matched_sequence_bodies = [
                row["nucleotide_sequence"]
                for row in read_tsv(publish_root / "tables" / "matched_sequences.tsv")
            ]
            call_protein_ids = {
                row["protein_id"]
                for row in read_tsv(publish_root / "calls" / "repeat_calls.tsv")
                if row.get("protein_id", "")
            }
            call_ids = {
                row["call_id"]
                for row in read_tsv(publish_root / "calls" / "repeat_calls.tsv")
                if row.get("call_id", "")
            }
            matched_protein_ids = {
                row["protein_id"]
                for row in read_tsv(publish_root / "tables" / "matched_proteins.tsv")
                if row.get("protein_id", "")
            }
            matched_protein_bodies = [
                row["amino_acid_sequence"]
                for row in read_tsv(publish_root / "tables" / "matched_proteins.tsv")
            ]
            context_call_ids = {
                row["call_id"]
                for row in read_tsv(publish_root / "tables" / "repeat_context.tsv")
                if row.get("call_id", "")
            }
            self.assertEqual(matched_sequence_ids, call_sequence_ids)
            self.assertEqual(matched_protein_ids, call_protein_ids)
            self.assertTrue(all(matched_sequence_bodies))
            self.assertTrue(all(matched_protein_bodies))
            self.assertEqual(context_call_ids, call_ids)
            self.assertFalse((publish_root / "database").exists())
            self.assertFalse((publish_root / "reports").exists())
            self._assert_dag_noise_within_limit(run_root / "internal" / "nextflow" / "dag.html")

    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_successful_explicit_merged_run_preserves_flat_acquisition_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_root = tmp / "run_merged"

            self._run_pipeline(
                run_root=run_root,
                accessions=["GCF_000001405.40", "GCF_000001635.27"],
                acquisition_publish_mode="merged",
            )

            publish_root = run_root / "publish"
            manifest = json.loads((publish_root / "metadata" / "run_manifest.json").read_text(encoding="utf-8"))
            launch = json.loads((publish_root / "metadata" / "launch_metadata.json").read_text(encoding="utf-8"))

            self.assertEqual(manifest["status"], "success")
            self.assertEqual(manifest["publish_contract_version"], 2)
            self.assertEqual(launch["publish_contract_version"], 2)
            self.assertEqual(manifest["acquisition_publish_mode"], "merged")
            self.assertEqual(launch["acquisition_publish_mode"], "merged")
            self.assertEqual(manifest["artifacts"]["acquisition"], {})
            self.assertEqual(manifest["artifacts"]["status"], {})
            self.assertEqual(manifest["artifacts"]["tables"]["genomes_tsv"], "publish/tables/genomes.tsv")
            self.assertEqual(
                manifest["artifacts"]["tables"]["repeat_call_codon_usage_tsv"],
                "publish/tables/repeat_call_codon_usage.tsv",
            )
            self.assertEqual(manifest["artifacts"]["tables"]["repeat_context_tsv"], "publish/tables/repeat_context.tsv")
            self.assertEqual(manifest["artifacts"]["summaries"]["status_summary_json"], "publish/summaries/status_summary.json")
            self.assertEqual(manifest["params"]["params_file_values"], {})
            self.assertEqual(manifest["params"]["effective_values"]["batch_size"], 1)
            self.assertFalse((publish_root / ".nf_placeholders").exists())

            self.assertFalse((publish_root / "acquisition").exists())
            self.assertFalse((publish_root / "status").exists())
            self.assertFalse((publish_root / "calls" / "finalized").exists())
            self.assertFalse(list(publish_root.rglob("cds.fna")))
            self.assertFalse(list(publish_root.rglob("proteins.faa")))
            self.assertTrue((publish_root / "calls" / "repeat_calls.tsv").is_file())
            self.assertTrue((publish_root / "calls" / "run_params.tsv").is_file())
            self.assertTrue((publish_root / "database" / "homorepeat.sqlite").is_file())
            self.assertTrue((publish_root / "database" / "sqlite_validation.json").is_file())
            self.assertTrue((publish_root / "reports" / "summary_by_taxon.tsv").is_file())
            self.assertTrue((publish_root / "reports" / "regression_input.tsv").is_file())
            self.assertTrue((publish_root / "reports" / "echarts_options.json").is_file())
            self.assertTrue((publish_root / "reports" / "echarts_report.html").is_file())
            self.assertTrue((publish_root / "reports" / "echarts.min.js").is_file())
            for filename in [
                "genomes.tsv",
                "taxonomy.tsv",
                "matched_sequences.tsv",
                "matched_proteins.tsv",
                "repeat_call_codon_usage.tsv",
                "repeat_context.tsv",
                "download_manifest.tsv",
                "normalization_warnings.tsv",
                "accession_status.tsv",
                "accession_call_counts.tsv",
            ]:
                self.assertTrue((publish_root / "tables" / filename).is_file(), publish_root / "tables" / filename)
            self.assertTrue((publish_root / "summaries" / "status_summary.json").is_file())
            self.assertTrue((publish_root / "summaries" / "acquisition_validation.json").is_file())
            self._assert_dag_noise_within_limit(run_root / "internal" / "nextflow" / "dag.html")

    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_missing_default_taxonomy_db_is_built_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_root = tmp / "run_auto_taxonomy"
            taxonomy_cache_dir = tmp / "taxonomy_cache"

            self._run_pipeline(
                run_root=run_root,
                accessions=["GCF_000001405.40"],
                supply_taxonomy_db=False,
                taxonomy_cache_dir=taxonomy_cache_dir,
            )

            self.assertTrue((taxonomy_cache_dir / "ncbi_taxonomy.sqlite").is_file())
            self.assertTrue((taxonomy_cache_dir / "taxdump.tar.gz").is_file())
            self.assertTrue((taxonomy_cache_dir / "ncbi_taxonomy_build.json").is_file())
            self.assertTrue((run_root / "publish" / "calls" / "repeat_calls.tsv").is_file())

    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_missing_explicit_taxonomy_db_fails_without_auto_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_root = tmp / "run_missing_explicit_taxonomy"
            accessions_file = tmp / "accessions.txt"
            missing_taxonomy_db = tmp / "missing_taxonomy.sqlite"
            nextflow_log = run_root / "internal" / "nextflow" / "nextflow.log"

            accessions_file.write_text("GCF_000001405.40\n", encoding="utf-8")
            env = {
                **CLI_ENV,
                "NXF_HOME": os.environ.get("NXF_HOME", str(REPO_ROOT / "runtime" / "cache" / "nextflow")),
            }
            result = subprocess.run(
                [
                    "nextflow",
                    "-log",
                    str(nextflow_log),
                    "run",
                    ".",
                    "-profile",
                    "local",
                    "--run_id",
                    run_root.name,
                    "--run_root",
                    str(run_root),
                    "--accessions_file",
                    str(accessions_file),
                    "--taxonomy_db",
                    str(missing_taxonomy_db),
                ],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("taxonomy database not found", result.stdout + result.stderr)
            self.assertFalse(missing_taxonomy_db.exists())

    def test_placeholder_publication_scaffold_stays_removed(self) -> None:
        executable_paths = [
            REPO_ROOT / "main.nf",
            REPO_ROOT / "lib" / "HomorepeatRuntimeArtifacts.groovy",
        ]
        forbidden_symbols = [
            "WORKFLOW_OUTPUT_PLACEHOLDER",
            "publishablePathChannel",
            "publishTarget",
            "workflow_output_placeholder",
            "cleanupWorkflowOutputPlaceholders",
            ".nf_placeholders",
        ]
        for path in executable_paths:
            text = path.read_text(encoding="utf-8")
            for symbol in forbidden_symbols:
                self.assertNotIn(symbol, text, f"{symbol} should not be reintroduced in {path}")

    def _assert_dag_noise_within_limit(self, dag_path: Path) -> None:
        dag_html = dag_path.read_text(encoding="utf-8")
        blank_nodes = BLANK_DAG_NODE_PATTERN.findall(dag_html)
        self.assertLessEqual(
            len(blank_nodes),
            MAX_EXPECTED_BLANK_DAG_NODES,
            f"{dag_path} contains {len(blank_nodes)} blank DAG nodes; sample: {blank_nodes[:20]}",
        )

    def _run_pipeline(
        self,
        *,
        run_root: Path,
        accessions: list[str],
        acquisition_publish_mode: str | None = None,
        supply_taxonomy_db: bool = True,
        taxonomy_cache_dir: Path | None = None,
    ) -> None:
        accessions_file = run_root.parent / "accessions.txt"
        taxonomy_db = run_root.parent / "taxonomy.sqlite"
        fake_bin_dir = run_root.parent / "fake_bin"
        nextflow_log = run_root / "internal" / "nextflow" / "nextflow.log"

        fake_bin_dir.mkdir(parents=True, exist_ok=True)
        run_root.mkdir(parents=True, exist_ok=True)
        accessions_file.write_text("\n".join(accessions) + "\n", encoding="utf-8")
        taxonomy_db.write_text("", encoding="utf-8")
        self._write_fake_datasets(fake_bin_dir / "datasets")
        self._write_fake_taxon_weaver(fake_bin_dir / "taxon-weaver")

        env = {
            **CLI_ENV,
            "PATH": f"{fake_bin_dir}:{CLI_ENV.get('PATH', '')}",
            "HOMOREPEAT_FIXTURES_ROOT": str(FIXTURES_ROOT),
            "NXF_HOME": os.environ.get("NXF_HOME", str(REPO_ROOT / "runtime" / "cache" / "nextflow")),
        }
        cmd = [
            "nextflow",
            "-log",
            str(nextflow_log),
            "run",
            ".",
            "-profile",
            "local",
            "--run_id",
            run_root.name,
            "--run_root",
            str(run_root),
            "--accessions_file",
            str(accessions_file),
            "--python_bin",
            sys.executable,
            "--datasets_bin",
            "datasets",
            "--taxon_weaver_bin",
            "taxon-weaver",
            "--batch_size",
            "1",
            "--run_pure",
            "true",
            "--run_threshold",
            "true",
            "--run_seed_extend",
            "false",
        ]
        if supply_taxonomy_db:
            cmd.extend(["--taxonomy_db", str(taxonomy_db)])
        if taxonomy_cache_dir:
            cmd.extend(["--taxonomy_cache_dir", str(taxonomy_cache_dir)])
        if acquisition_publish_mode:
            cmd.extend(["--acquisition_publish_mode", acquisition_publish_mode])

        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                f"nextflow publish-mode workflow failed with exit code {result.returncode}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

    def _write_fake_datasets(self, path: Path) -> None:
        script = textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import os
            import pathlib
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
                if accessions == {"GCF_000001405.40"}:
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
            import pathlib
            import sys

            args = sys.argv[1:]
            if args[:1] == ["build-db"]:
                dump = args[args.index("--dump") + 1]
                db = args[args.index("--db") + 1]
                report = args[args.index("--report-json") + 1]
                pathlib.Path(dump).write_text("fake taxdump\\n", encoding="utf-8")
                pathlib.Path(db).write_text("fake sqlite\\n", encoding="utf-8")
                pathlib.Path(report).write_text(json.dumps({"taxonomy_build_version": "2026-04-05"}), encoding="utf-8")
                raise SystemExit(0)

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
