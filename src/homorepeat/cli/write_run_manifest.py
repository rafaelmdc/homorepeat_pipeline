#!/usr/bin/env python3
"""Write a published run manifest for one completed pipeline run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from homorepeat.runtime.run_manifest import build_run_manifest, write_run_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-root", required=True, help="Pipeline root")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument("--run-root", required=True, help="Run root directory")
    parser.add_argument("--publish-root", required=True, help="Published artifact root")
    parser.add_argument("--profile", required=True, help="Active Nextflow profile")
    parser.add_argument("--accessions-file", required=True, help="Accessions input file")
    parser.add_argument("--taxonomy-db", required=True, help="Taxonomy SQLite input")
    parser.add_argument("--launch-metadata", required=True, help="Normalized Nextflow launch metadata path")
    parser.add_argument("--started-at-utc", required=True, help="Run start timestamp")
    parser.add_argument("--finished-at-utc", required=True, help="Run finish timestamp")
    parser.add_argument("--status", default="success", help="Final run status")
    parser.add_argument(
        "--acquisition-publish-mode",
        default="raw",
        help="Acquisition publish mode: raw or merged",
    )
    parser.add_argument("--params-file", help="Optional params file")
    parser.add_argument(
        "--effective-params-json",
        help="Optional JSON object describing the effective runtime params after CLI overrides",
    )
    parser.add_argument("--outpath", required=True, help="Manifest output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    effective_params = None
    if args.effective_params_json:
        effective_params = json.loads(args.effective_params_json)
        if not isinstance(effective_params, dict):
            raise ValueError("--effective-params-json must decode to a JSON object")
    payload = build_run_manifest(
        repo_root=Path(args.pipeline_root),
        run_id=args.run_id,
        run_root=Path(args.run_root),
        publish_root=Path(args.publish_root),
        profile=args.profile,
        accessions_file=Path(args.accessions_file),
        taxonomy_db=Path(args.taxonomy_db),
        params_file=Path(args.params_file) if args.params_file else None,
        launch_metadata=Path(args.launch_metadata),
        started_at_utc=args.started_at_utc,
        finished_at_utc=args.finished_at_utc,
        status=args.status,
        acquisition_publish_mode=args.acquisition_publish_mode,
        effective_params=effective_params,
    )
    write_run_manifest(args.outpath, payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
