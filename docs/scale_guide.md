## Scale the Pipeline for ~900 Genomes on One Docker Host

  ### Summary

  - Current state: the pipeline is already capable of parallel batch acquisition, because workflows/acquisition_from_accessions.nf fans out batch manifests into separate download/normalize/translate tasks. Detection is not batch-
    parallel today, because workflows/detection_from_acquisition.nf waits for the merged acquisition outputs and then scans one monolithic protein set per method/residue.
  - Keep the published flat-file contracts unchanged. This is a workflow/config scaling change, not a schema change.
  - Target runtime: one machine, docker profile.
  - Chosen scaling policy: make acquisition and detection both batch-parallel, and change the default batch_size from 100 to 25 for better load balancing across ~900 genomes.

  ### Key Changes

  - In workflows/acquisition_from_accessions.nf, keep the existing merged outputs, but also emit the per-batch translated channel as an internal workflow interface for downstream detection.
  - Refactor workflows/detection_from_acquisition.nf to consume per-batch inputs keyed by batch_id:
      - Run DETECT_* per batch_id x method x repeat_residue.
      - Run FINALIZE_CALL_CODONS per batch_id x method x repeat_residue.
      - Merge all finalized call fragments and run-param fragments with the existing MERGE_CALL_TABLES step before reporting.
  - Do not change call identity rules. Existing call_id generation is already stable across per-batch execution, so merged repeat_calls.tsv remains contract-compatible.
  - In conf/base.config:
      - Change params.batch_size default to 25.
      - Add explicit maxForks controls by label:
          - planning: 1
          - acquisition_download: 2
          - acquisition_normalize: 4
          - acquisition_merge: 1
          - detection: 4
          - database: 1
          - reporting: 1
      - Keep cpus = 1 per task unless profiling shows a specific CLI benefits from internal multithreading later.
  - Keep the wrapper unchanged. scripts/run_phase4_pipeline.sh already passes through extra Nextflow args, so -resume remains the operational recovery path for large runs.
  - Add an operator note in docs that for large runs the intended shape is many small batch tasks plus -resume, not one giant merged detection pass.

  ### Public / Interface Changes

  - No changes to published artifacts under publish/acquisition/, publish/calls/, publish/database/, or publish/reports/.
  - Internal workflow interface change only:
      - acquisition workflow emits per-batch translated outputs for detection.
      - detection workflow consumes batch-keyed inputs instead of only merged acquisition tables.
  - Config surface additions:
      - new default batch_size = 25
      - new per-label concurrency limits via maxForks

  ### Test Plan

  - Add/update workflow-level tests to confirm the pipeline still parses and that batch-parallel detection wiring composes correctly.
  - Add a targeted CLI/workflow regression test that runs two small translated batches through detection/finalization and verifies:
      - merged repeat_calls.tsv is identical to the old single-merged-input behavior for the same fixtures
      - merged run_params.tsv remains de-duplicated and conflict-free
  - Add a runtime/integration test that verifies multiple batch manifests produce multiple DOWNLOAD_NCBI_BATCH and NORMALIZE_CDS_BATCH tasks, and that detection now produces multiple finalized fragments before merge.
  - Acceptance criteria for a real 900-genome run:
      - Nextflow timeline shows concurrent download, normalize, and detection tasks
      - final published outputs remain in the same locations and schemas
      - rerunning with -resume skips completed batch tasks cleanly

  ### Assumptions

  - The main scaling bottleneck worth fixing first is workflow structure, not Python algorithm speed.
  - One-host Docker is the target; no scheduler/cloud executor migration is included in this pass.
  - Smaller batches (25) are preferred over 50 or 100 to maximize balancing and resumability for a 900-genome run.
  - Official Nextflow behavior should be relied on for task-level concurrency under the local executor and for maxForks caps:
      - https://nextflow.io/docs/stable/reference/process.html
