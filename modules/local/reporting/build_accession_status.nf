process BUILD_ACCESSION_STATUS {
    label 'reporting'

    input:
    path(batch_table)
    path(batch_dirs, stageAs: 'batch??')
    path(call_tsvs, stageAs: 'call??.tsv')
    path(detect_status_jsons, stageAs: 'detect_status??.json')
    path(finalize_status_jsons, stageAs: 'finalize_status??.json')

    output:
    path('accession_status.tsv'), emit: accession_status_tsv
    path('accession_call_counts.tsv'), emit: accession_call_counts_tsv
    path('status_summary.json'), emit: status_summary_json

    script:
    def batchInputs = batch_dirs instanceof List ? batch_dirs : [batch_dirs]
    def callInputs = call_tsvs instanceof List ? call_tsvs : [call_tsvs]
    def detectInputs = detect_status_jsons instanceof List ? detect_status_jsons : [detect_status_jsons]
    def finalizeInputs = finalize_status_jsons instanceof List ? finalize_status_jsons : [finalize_status_jsons]
    def batchArgs = batchInputs.collect { "--batch-dir '${it}'" }.join(' ')
    def callArgs = callInputs.collect { "--call-tsv '${it}'" }.join(' ')
    def detectArgs = detectInputs.collect { "--detect-status-json '${it}'" }.join(' ')
    def finalizeArgs = finalizeInputs.collect { "--finalize-status-json '${it}'" }.join(' ')
    """
    ${params.python_bin} -m homorepeat.cli.build_accession_status \
      --batch-table ${batch_table} \
      ${batchArgs} \
      ${callArgs} \
      ${detectArgs} \
      ${finalizeArgs} \
      --outdir status_tmp

    mv status_tmp/accession_status.tsv accession_status.tsv
    mv status_tmp/accession_call_counts.tsv accession_call_counts.tsv
    mv status_tmp/status_summary.json status_summary.json
    """
}
