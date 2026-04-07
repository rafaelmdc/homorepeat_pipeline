# Repeat Detection Expansion Slices

## Purpose

This document breaks the roadmap into reviewable implementation slices. Each slice is intended to be small enough to land cleanly and validate in isolation.

## Slice 1: Surface Existing Detection Parameters

### Goal

Expose the current `pure` and `threshold` tuning knobs through pipeline config, Nextflow modules, CLI invocation, and `run_params.tsv`.

### Scope

- `conf/base.config`
- `modules/local/detection/detect_pure.nf`
- `modules/local/detection/detect_threshold.nf`
- `src/homorepeat/cli/detect_pure.py`
- `src/homorepeat/cli/detect_threshold.py`
- tests that assert run params and CLI behavior

### Changes

- add `params.pure_min_repeat_count`
- add `params.threshold_window_size`
- add `params.threshold_min_target_count`
- pass them from Nextflow into the Python CLIs
- ensure method-specific `run_params.tsv` reflects these values

### Acceptance criteria

- pipeline params can override pure minimum size
- pipeline params can override threshold window and count
- `run_params.tsv` records the actual values used
- existing defaults stay unchanged when params are not supplied

### Validation

- `tests/unit/test_slice3_pure_detection.py`
- `tests/unit/test_slice4_threshold_detection.py`
- `tests/cli/test_runtime_artifacts.py`

## Slice 2: Add Seed-Extend Detection Core

### Goal

Introduce a separate `seed_extend` library implementation with deterministic boundaries and method-specific tests.

### Scope

- new detection library module under `src/homorepeat/detection/`
- unit tests for seed finding, extension, trimming, and de-duplication

### Changes

- add tract dataclass for `seed_extend`
- implement seed discovery
- implement left and right extension
- merge overlapping or adjacent seed-extended candidates
- trim final tracts to leading and trailing `Q`

### Acceptance criteria

- the method reports long interrupted tracts that `pure` misses
- the method remains stricter than naive threshold-only merging
- output coordinates are 1-based, inclusive, and deterministic

### Validation

- new unit tests focused on:
  - one clear seed
  - multiple overlapping seeds
  - extension to sequence edges
  - rejection of weak Q-rich noise
  - trim behavior when seeds include flanking non-Q residues

## Slice 3: Wire Seed-Extend Into CLI and Workflow

### Goal

Make the new method runnable end-to-end like the existing detection methods.

### Scope

- new CLI under `src/homorepeat/cli/`
- new Nextflow module under `modules/local/detection/`
- `workflows/detection_from_acquisition.nf`
- `main.nf` outputs if needed
- run-param helpers and tests

### Changes

- add `homorepeat.cli.detect_seed_extend`
- add `params.run_seed_extend`
- add method-specific params:
  - `seed_extend_seed_window_size`
  - `seed_extend_seed_min_target_count`
  - `seed_extend_extend_window_size`
  - `seed_extend_extend_min_target_count`
  - `seed_extend_min_total_length`
- emit finalized call tables and run params for the new method

### Acceptance criteria

- the method can be enabled or disabled independently
- it produces call rows with the same core schema as other methods
- `run_params.tsv` records all seed-extend settings
- merged canonical calls include the new method without schema drift

### Validation

- new CLI test for seed-extend output
- `tests/cli/test_runtime_artifacts.py`
- `tests/workflow/test_pipeline_config.py`

## Slice 4: Add Codon-Usage Analysis Outputs

### Goal

Produce per-finding codon usage statistics for every amino acid represented in the called tract.

### Scope

- `src/homorepeat/detection/codon_extract.py`
- `src/homorepeat/cli/extract_repeat_codons.py`
- new codon-usage contract helper if useful
- tests for codon usage extraction

### Changes

- add a helper that converts a successful `codon_sequence` into codon counts by amino acid
- write a new `codon_usage.tsv` artifact alongside finalized call tables
- keep warning behavior unchanged when codon extraction fails

### Acceptance criteria

- successful finalized calls produce codon-usage rows
- each row reports `%` as `codon_fraction`
- fractions sum to `1` within each `call_id` plus `amino_acid` group
- pure polyQ calls report `CAA` and `CAG` usage cleanly
- impure tracts report codons for interruption residues as well

### Validation

- extend `tests/unit/test_slice6_codon_extraction.py`
- add CLI assertions for `codon_usage.tsv`

## Slice 5: Reorganize Published Detection Outputs

### Goal

Separate method-specific finalized outputs from canonical merged call exports.

### Scope

- `modules/local/detection/extract_repeat_codons.nf`
- `workflows/detection_from_acquisition.nf`
- `src/homorepeat/runtime/run_manifest.py`
- smoke scripts
- operations and contracts docs
- runtime artifact tests

### Changes

- publish finalized method outputs under `publish/detection/finalized/<method>/<repeat_residue>/`
- leave canonical merged tables under `publish/calls/`
- include `codon_usage.tsv` in finalized method output directories
- update run manifest artifact collection if method-finalized artifacts are added there

### Acceptance criteria

- method-specific outputs no longer live under `publish/calls/`
- downstream reporting still reads canonical merged outputs from `publish/calls/`
- smoke scripts and runtime artifact tests match the new layout

### Validation

- `tests/cli/test_runtime_artifacts.py`
- smoke script path assertions
- optional end-to-end smoke run if the local environment is available

## Slice 6: Contract and Operator Docs

### Goal

Bring the stable docs into line with the implemented behavior.

### Scope

- `docs/contracts.md`
- `docs/methods.md`
- `docs/operations.md`
- optional architecture doc touch-up if the new method is now part of the supported set

### Changes

- document the new method and parameters
- document the `codon_usage.tsv` schema
- document the reorganized publish layout
- document which outputs are canonical versus method-specific

### Acceptance criteria

- docs match the shipped file paths and method names
- no doc still claims codon metric fields are always blank if codon usage is now emitted
- operator docs reflect the actual published layout

### Validation

- manual doc review against current code paths
- targeted test updates where docs are indirectly asserted by runtime-manifest tests

## Slice dependencies

- Slice 1 should land before Slice 3
- Slice 2 should land before Slice 3
- Slice 4 can land before or after Slice 5
- Slice 6 should land with the final behavior, not ahead of it

## Recommended PR grouping

If this work is split across multiple PRs, use this grouping:

1. Slice 1
2. Slices 2 and 3 together
3. Slice 4
4. Slices 5 and 6 together
