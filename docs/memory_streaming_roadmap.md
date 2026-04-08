# Remaining Memory Streaming Roadmap

## Purpose

This roadmap captures the remaining memory work after the first performance pass.

The first pass fixed the biggest acquisition issues:

- normalize and translate no longer build large output payload lists before writing
- translated batches no longer duplicate the normalized batch directory
- acquisition starts detection batch-by-batch instead of waiting for all batches
- safer resource defaults now ship in `conf/base.config`

The pipeline is in a much better state, but it is not fully streamed end to end yet.

## What the current live run shows

The one-accession canonical live run on April 8, 2026 completed successfully at:

- [`runs/live_nextflow_small_2026_04_08_03`](../runs/live_nextflow_small_2026_04_08_03)

Its trace still shows a few stages that hold more data than they need to:

- `NORMALIZE_CDS_BATCH`: `531.7 MB peak_rss`
- `TRANSLATE_CDS_BATCH`: `218.7 MB peak_rss`
- `FINALIZE_PURE_CALL_CODONS`: `258.2 MB peak_rss`
- `FINALIZE_THRESHOLD_CALL_CODONS`: `258.9 MB peak_rss`
- `BUILD_SQLITE`: `230.1 MB peak_rss`
- `BUILD_ACCESSION_STATUS`: `197.6 MB peak_rss`

Those numbers are not dangerous by themselves on a one-accession run, but they show where the remaining full-file materialization still lives.

## Remaining problem statement

The pipeline still has four classes of memory behavior that should be fixed:

1. detection CLIs still load full protein TSV and FASTA inputs and accumulate all call rows before writing
2. codon finalization still loads full call tables, full sequence tables, and the full CDS FASTA into memory
3. terminal reducers still materialize full canonical tables for merge, summaries, status, and SQLite import
4. the detection workflow still uses end-of-run `toList()` reductions for finalized paths and stage status collections

The next phase should finish the line-by-line or batch-bounded shape of the runtime path before attempting larger benchmark reruns.

## Design principles

### 1. Stream where order is already canonical

When an upstream stage already writes deterministic row order, downstream stages should consume that order directly instead of loading all rows only to sort them again.

Examples:

- `proteins.tsv` and `proteins.faa`
- finalized call tables written per method, residue, and batch
- per-batch `sequences.tsv` and `cds.fna`

### 2. Keep unavoidable state narrow and keyed

Some stages cannot be purely stateless because they need lookups or de-duplication.

That is acceptable when the retained state is:

- keyed by one contract identifier such as `sequence_id` or `protein_id`
- bounded to one batch or one finalized fragment
- much smaller than loading the whole source file payloads into memory

### 3. Push full reductions to the real end

Merging canonical calls, building summaries, and building SQLite are terminal tasks.

They can still be improved, but they should not block earlier task fan-out and they should not force large upstream stages to carry extra in-memory state.

### 4. Optimize the runtime path before polishing report paths

The current highest-priority targets are:

- detection
- codon finalization
- workflow reduction barriers

Summary and SQLite builders matter too, but they are later than the repeat-detection hot path.

## Target outcome

After this phase:

- detection and codon finalization should operate in a streamed or bounded-batch shape
- no stage on the hot path should require loading whole FASTA payloads into dicts just to process one batch
- end-of-run reducers should be the only places that still need broader table aggregation
- larger benchmark reruns should be much less likely to hit memory cliffs from non-acquisition stages

## Recommended architecture changes

### Detection CLIs

`detect_pure`, `detect_threshold`, and `detect_seed_extend` should:

- iterate `proteins.tsv` and `proteins.faa` in lockstep
- validate that both artifacts stay aligned by `protein_id`
- write call rows incrementally
- avoid building one giant `call_rows` list

### Codon finalization

`extract_repeat_codons` should:

- avoid loading the entire CDS FASTA into memory
- write enriched calls, warnings, and codon-usage rows incrementally
- keep only lookup state that is truly needed for one finalized fragment
- prefer sequence-grouped processing over global whole-file materialization

### Reporting and database reducers

`merge_call_tables`, `export_summary_tables`, `build_accession_status`, and `build_sqlite` should:

- stream or append where possible
- keep dedup maps or counters instead of full row lists when validation allows
- remain terminal reducers, but stop loading more data than needed

### Workflow reductions

`DETECTION_FROM_ACQUISITION` should stop using `toList()` for finalized path and status fan-in unless a downstream process absolutely requires one list-valued channel.

The preferred pattern is:

- keep finalized directories streaming
- reduce only inside the exact reporting/status/database task that needs aggregate inputs

## Delivery order

Recommended order of work:

1. stream detection CLIs
2. stream codon finalization
3. remove remaining detection-workflow `toList()` barriers
4. stream end-of-run reducers for call merge, status, summaries, and SQLite
5. rerun the chromosome benchmark and compare against the existing baseline

## Success criteria

This phase is successful when all of the following are true:

- detection no longer loads whole protein FASTA payloads into memory
- codon finalization no longer builds a full CDS FASTA dict for each finalized fragment
- the detection workflow emits finalized outputs without a global list barrier
- the chromosome benchmark still produces stable canonical outputs
- the benchmark shows no new high-memory regressions outside normalize
