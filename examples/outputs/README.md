# Output Examples

This directory contains tiny representative snippets of the published output
layout. They are examples for orientation, not benchmark results.

The real pipeline writes outputs under:

```text
runs/<run_id>/publish/
```

Representative files here:

| File | Use |
| --- | --- |
| `publish/START_HERE.md` | Run-specific orientation file |
| `publish/calls/repeat_calls.tsv` | Main repeat-call table |
| `publish/calls/run_params.tsv` | Detection parameters by method and residue |
| `publish/tables/accession_status.tsv` | Per-accession terminal status |
| `publish/tables/accession_call_counts.tsv` | Per-accession call counts by method/residue |
| `publish/summaries/status_summary.json` | Run-level status summary |

Open `repeat_calls.tsv` for biological calls, then check
`accession_status.tsv` to distinguish failed accessions from successful
accessions with no matching repeats.
