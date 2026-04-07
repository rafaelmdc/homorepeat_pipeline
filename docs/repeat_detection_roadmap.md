# Repeat Detection Expansion Roadmap

## Purpose

This roadmap scopes the next detection and output changes:

- add a new residue-aware seed-extend method
- expose runtime parameters for the existing `pure` and `threshold` methods
- clean up published pipeline outputs and workflow emits
- add per-finding codon-usage statistics

The current gap is not one isolated bug. The codebase is still shaped around the initial two-method release:

- detection orchestration only wires `pure` and `threshold`
- Nextflow params do not yet expose the main tuning knobs for each method
- finalized call rows reserve codon metric fields but the implementation leaves them empty
- method-level finalized outputs now publish under `publish/detection/finalized/...`, while canonical merged outputs remain under `publish/calls/`

## Target outcome

After this work, one run should produce:

- parameterized `pure` detection
- parameterized `threshold` detection
- a new `seed_extend` detection path for long interrupted tracts
- a cleaner separation between method-specific detection outputs and canonical merged outputs
- codon-usage outputs that report, for each finding, the fraction of each codon observed in the tract

## Recommended method design

### 1. Pure method

Keep the current contiguous-run behavior, but surface the minimum tract size as a pipeline-level parameter instead of leaving it only inside the CLI.

Recommended parameter:

- `pure_min_repeat_count`

Default:

- `6`

### 2. Threshold method

Keep the current sliding-window density logic, but make the threshold explicit in pipeline params and run metadata.

Recommended parameters:

- `threshold_window_size`
- `threshold_min_target_count`

Default:

- `8`
- `6`

Recorded threshold string:

- `<residue><min_target_count>/<window_size>`
- example: `Q6/8`

### 3. New seed-extend method

This method should be introduced as a separate method rather than folding extra behavior into `threshold`.

Recommended first implementation:

- method name: `seed_extend`
- scope: residue-aware from the start
- seed rule: find windows with strong Q density
- extension rule: once a qualifying seed is found, extend left and right while the local tract remains above a looser density rule and still starts/ends on `Q`

Recommended parameters:

- `seed_extend_seed_window_size`
- `seed_extend_seed_min_target_count`
- `seed_extend_extend_window_size`
- `seed_extend_extend_min_target_count`
- `seed_extend_min_total_length`

Recommended defaults:

- `seed_extend_seed_window_size = 8`
- `seed_extend_seed_min_target_count = 6`
- `seed_extend_extend_window_size = 12`
- `seed_extend_extend_min_target_count = 8`
- `seed_extend_min_total_length = 10`

Rationale:

- the seed should be strict enough to avoid weak background Q density
- the extension rule should be looser than the seed so interrupted but clearly repeat-rich tracts can grow
- `seed_extend` should remain distinct from `threshold`: seed finds candidate cores, extension turns those cores into long reported tracts

Open design decision to confirm during implementation:

- whether extension should advance one residue at a time or one window at a time

Recommendation:

- implement one-residue extension with a rolling density check, because it is easier to test and gives deterministic tract boundaries

## Parameter surfacing plan

Runtime params should be available in three places:

- `conf/base.config`
- Nextflow modules that invoke detection CLIs
- `run_params.tsv` outputs for each method

The goal is that no biologically meaningful detection threshold remains hard-coded only inside Python defaults.

## Output reorganization

The current layout mixes canonical outputs and method-specific finalized outputs under `publish/calls/`.

Recommended target layout:

- `publish/acquisition/`
- `publish/detection/finalized/<method>/<repeat_residue>/`
- `publish/calls/`
- `publish/database/sqlite/`
- `publish/reports/`
- `publish/manifest/`

Recommended contents:

- `publish/detection/finalized/<method>/<repeat_residue>/`
  - finalized call table for that method and residue
  - method run params
  - codon warnings
  - codon-usage table
- `publish/calls/`
  - `repeat_calls.tsv`
  - `run_params.tsv`

Why this is cleaner:

- `publish/detection/` becomes the home for method-specific artifacts
- `publish/calls/` becomes the stable canonical interface for downstream database and reporting stages
- the run manifest can clearly distinguish canonical call artifacts from per-method finalized artifacts

## Codon analysis roadmap

The current `codon_metric_name` and `codon_metric_value` fields are too narrow for the requested analysis.

One finding can contain several codons for the same amino acid, so storing only one metric pair in the main call row will not scale. The clean contract is a normalized companion table.

Recommended new artifact:

- `codon_usage.tsv`

Recommended row grain:

- one row per `call_id`, `amino_acid`, `codon`

Recommended columns:

- `call_id`
- `method`
- `repeat_residue`
- `sequence_id`
- `protein_id`
- `amino_acid`
- `codon`
- `codon_count`
- `codon_fraction`

Behavior:

- derive counts directly from `codon_sequence`
- translate codons back to amino acids using the call translation table
- report fractions within each amino acid observed in the tract
- for pure polyQ calls, this will naturally produce the per-call `% CAA` and `% CAG`
- for impure tracts, the output will also cover interruption residues

Compatibility recommendation:

- keep `codon_metric_name` and `codon_metric_value` in the call contract for now
- leave them blank until there is a strong reason to promote one derived metric into the main call row

## Contract impacts

Files that will need contract updates:

- `docs/contracts.md`
- `docs/methods.md`
- `docs/operations.md`
- `src/homorepeat/runtime/run_manifest.py`

Main contract additions:

- `method` allowed values must include `seed_extend`
- documented pipeline params for all detection methods
- documented finalized detection output layout
- new `codon_usage.tsv` contract

## Validation strategy

Validation should stay narrow and grow only if needed.

Recommended order:

1. unit tests for pure, threshold, and seed-extend detection behavior
2. unit tests for codon-usage extraction from finalized calls
3. CLI tests for each detection method and codon extraction outputs
4. runtime artifact tests for the reorganized publish layout and manifest contents
5. optional Nextflow config parse check

## Risks

- the seed-extend method can drift into a second threshold method unless the extension rule is clearly distinct
- changing publish paths can break smoke scripts, operations docs, and manifest expectations
- forcing codon percentages into the existing call table would create an unstable schema; a companion table is safer
- if the new method is made residue-neutral immediately, the parameter surface and tests grow faster than needed

## Recommended delivery order

1. expose pure and threshold params end-to-end
2. add the new seed-extend polyQ method
3. add codon-usage outputs
4. move finalized method artifacts under `publish/detection/`
5. update docs, smoke scripts, and manifest expectations together
