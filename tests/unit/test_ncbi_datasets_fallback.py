from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

from homorepeat.acquisition.ncbi_datasets import download_genome_batch, summary_genome_accession


class NCBIDatasetsFallbackTest(unittest.TestCase):
    def test_summary_genome_accession_falls_back_to_rest_after_cli_failure(self) -> None:
        requests: list[dict[str, object]] = []
        reports = [
            {
                "accession": "GCF_000001405.40",
                "assemblyInfo": {"assemblyLevel": "Chromosome"},
                "organism": {"taxId": 9606, "organismName": "Homo sapiens"},
            }
        ]

        def fake_urlopen(request, timeout=600):  # type: ignore[no-untyped-def]
            requests.append(
                {
                    "url": request.full_url,
                    "headers": dict(request.header_items()),
                    "body": json.loads((request.data or b"{}").decode("utf-8")),
                    "timeout": timeout,
                }
            )
            if len(requests) == 1:
                payload = json.dumps(
                    {
                        "error": "Too Many Requests",
                        "code": 429,
                        "message": "Too many requests",
                    }
                ).encode("utf-8")
                raise HTTPError(
                    request.full_url,
                    429,
                    "Too Many Requests",
                    {"Retry-After": "0"},
                    io.BytesIO(payload),
                )
            payload = json.dumps({"reports": reports, "total_count": 1}).encode("utf-8")
            return _FakeHTTPResponse(payload, headers={"Content-Type": "application/json"})

        with mock.patch(
            "homorepeat.acquisition.ncbi_datasets.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=["datasets"],
                returncode=1,
                stdout="",
                stderr="Error: [gateway] giving up after 11 attempt(s)",
            ),
        ):
            with mock.patch("homorepeat.acquisition.ncbi_datasets.urllib.request.urlopen", side_effect=fake_urlopen):
                records, raw_lines = summary_genome_accession(
                    "GCF_000001405.40",
                    max_attempts=2,
                    retry_delay_seconds=0,
                    api_base_url="https://example.test/datasets/v2",
                )

        self.assertEqual([record["accession"] for record in records], ["GCF_000001405.40"])
        self.assertEqual(len(raw_lines), 1)
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]["url"], "https://example.test/datasets/v2/genome/dataset_report")
        self.assertEqual(
            requests[0]["body"],
            {
                "accessions": ["GCF_000001405.40"],
                "filters": {
                    "assembly_source": "refseq",
                    "assembly_version": "current",
                    "has_annotation": True,
                },
                "page_size": 1000,
                "returned_content": "COMPLETE",
            },
        )

    def test_download_genome_batch_falls_back_to_rest_zip_after_cli_failure(self) -> None:
        requests: list[dict[str, object]] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            accessions_file = tmp / "selected_accessions.txt"
            output_zip = tmp / "batch.zip"
            accessions_file.write_text("GCF_000001405.40\n", encoding="utf-8")

            def fake_urlopen(request, timeout=600):  # type: ignore[no-untyped-def]
                requests.append(
                    {
                        "url": request.full_url,
                        "headers": dict(request.header_items()),
                        "body": json.loads((request.data or b"{}").decode("utf-8")),
                        "timeout": timeout,
                    }
                )
                return _FakeHTTPResponse(
                    _build_test_package_zip(),
                    headers={"Content-Type": "application/zip"},
                )

            with mock.patch(
                "homorepeat.acquisition.ncbi_datasets.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=["datasets"],
                    returncode=1,
                    stdout="",
                    stderr="Error: [gateway] giving up after 11 attempt(s)",
                ),
            ):
                with mock.patch("homorepeat.acquisition.ncbi_datasets.urllib.request.urlopen", side_effect=fake_urlopen):
                    download_genome_batch(
                        accessions_file,
                        output_zip,
                        include="cds,gff3,seq-report",
                        max_attempts=1,
                        retry_delay_seconds=0,
                        api_base_url="https://example.test/datasets/v2",
                    )

            self.assertTrue(output_zip.is_file())
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0]["url"], "https://example.test/datasets/v2/genome/download")
            self.assertEqual(
                requests[0]["body"],
                {
                    "accessions": ["GCF_000001405.40"],
                    "include_annotation_type": ["CDS_FASTA", "GENOME_GFF", "SEQUENCE_REPORT"],
                },
            )
            with zipfile.ZipFile(output_zip) as archive:
                self.assertIn("ncbi_dataset/data/assembly_data_report.jsonl", archive.namelist())
                self.assertIn("ncbi_dataset/data/GCF_000001405.40/cds_from_genomic.fna", archive.namelist())
                self.assertIn("ncbi_dataset/data/GCF_000001405.40/genomic.gff", archive.namelist())


def _build_test_package_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "ncbi_dataset/data/assembly_data_report.jsonl",
            json.dumps({"accession": "GCF_000001405.40"}) + "\n",
        )
        archive.writestr("ncbi_dataset/data/GCF_000001405.40/cds_from_genomic.fna", ">cds\nATG\n")
        archive.writestr("ncbi_dataset/data/GCF_000001405.40/genomic.gff", "##gff-version 3\n")
        archive.writestr("ncbi_dataset/data/GCF_000001405.40/sequence_report.jsonl", json.dumps({"accession": "NC_1"}) + "\n")
    return buffer.getvalue()


class _FakeHTTPResponse(io.BytesIO):
    def __init__(self, payload: bytes, *, headers: dict[str, str]) -> None:
        super().__init__(payload)
        self.headers = headers

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()


if __name__ == "__main__":
    unittest.main()
