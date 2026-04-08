from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_support import CLI_ENV, REPO_ROOT


class BenchmarkSummaryCliTest(unittest.TestCase):
    def test_summarize_benchmark_run_reports_trace_milestones_and_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            trace_path = tmp / "trace.txt"
            accessions_file = tmp / "accessions.txt"
            size_root = tmp / "size_root"
            outpath = tmp / "summary.json"

            trace_path.write_text(
                "\n".join(
                    [
                        "task_id\thash\tnative_id\tname\tstatus\texit\tsubmit\tduration\trealtime\t%cpu\tpeak_rss\tpeak_vmem\trchar\twchar",
                        "1\taa/000001\t1001\tACQUISITION_FROM_ACCESSIONS:PLAN_ACCESSION_BATCHES\tCOMPLETED\t0\t2026-04-08 10:00:00.000\t1s\t1s\t100.0%\t10 MB\t20 MB\t1 MB\t1 MB",
                        "2\taa/000002\t1002\tACQUISITION_FROM_ACCESSIONS:NORMALIZE_CDS_BATCH (batch_0001)\tCOMPLETED\t0\t2026-04-08 10:00:15.000\t5s\t5s\t100.0%\t1.5 GB\t2 GB\t1 MB\t1 MB",
                        "3\taa/000003\t1003\tACQUISITION_FROM_ACCESSIONS:TRANSLATE_CDS_BATCH (batch_0001)\tCOMPLETED\t0\t2026-04-08 10:00:25.000\t7s\t7s\t100.0%\t512 MB\t1 GB\t1 MB\t1 MB",
                        "4\taa/000004\t1004\tDETECTION_FROM_ACQUISITION:DETECT_PURE (batch_0001,Q)\tCOMPLETED\t0\t2026-04-08 10:00:40.000\t9s\t9s\t100.0%\t128 MB\t512 MB\t1 MB\t1 MB",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            accessions_file.write_text("GCF_1\nGCF_2\nGCF_3\n", encoding="utf-8")
            size_root.mkdir(parents=True, exist_ok=True)
            (size_root / "a.bin").write_bytes(b"abcd")
            nested = size_root / "nested"
            nested.mkdir(parents=True, exist_ok=True)
            (nested / "b.bin").write_bytes(b"efghij")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homorepeat.cli.summarize_benchmark_run",
                    "--trace",
                    str(trace_path),
                    "--accessions-file",
                    str(accessions_file),
                    "--size-path",
                    str(size_root),
                    "--outpath",
                    str(outpath),
                ],
                cwd=REPO_ROOT,
                env=CLI_ENV,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.fail(
                    f"summarize_benchmark_run failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            payload = json.loads(outpath.read_text(encoding="utf-8"))
            self.assertEqual(payload["benchmark_input"]["n_accessions"], 3)
            self.assertEqual(payload["sizes"][str(size_root)]["bytes"], 10)
            self.assertEqual(payload["trace"]["n_tasks"], 4)
            self.assertEqual(payload["trace"]["n_completed_tasks"], 4)
            self.assertEqual(
                payload["trace"]["peak_rss_by_process"]["ACQUISITION_FROM_ACCESSIONS:NORMALIZE_CDS_BATCH"][
                    "max_peak_rss_bytes"
                ],
                1610612736,
            )
            self.assertEqual(
                payload["trace"]["milestones"]["time_to_first_normalize_completion_seconds"],
                20.0,
            )
            self.assertEqual(
                payload["trace"]["milestones"]["time_to_first_translate_completion_seconds"],
                32.0,
            )
            self.assertEqual(
                payload["trace"]["milestones"]["time_to_first_detection_completion_seconds"],
                49.0,
            )


if __name__ == "__main__":
    unittest.main()
