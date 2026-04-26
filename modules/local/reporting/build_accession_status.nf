process BUILD_ACCESSION_STATUS_TASK {
    label 'reporting'

    input:
    path(batch_table)
    tuple val(batch_ids), path(normalized_batch_dirs, stageAs: 'normalized_batch??'), path(translated_batch_dirs, stageAs: 'translated_batch??')
    path(call_tsvs, stageAs: 'call??.tsv')
    path(detect_status_jsons, stageAs: 'detect_status??.json')
    path(finalize_status_jsons, stageAs: 'finalize_status??.json')

    output:
    path('accession_status.tsv'), emit: accession_status_tsv
    path('accession_call_counts.tsv'), emit: accession_call_counts_tsv
    path('status_summary.json'), emit: status_summary_json

    script:
    def batchIdInputs = batch_ids instanceof List ? batch_ids : [batch_ids]
    def normalizedInputs = normalized_batch_dirs instanceof List ? normalized_batch_dirs : [normalized_batch_dirs]
    def translatedInputs = translated_batch_dirs instanceof List ? translated_batch_dirs : [translated_batch_dirs]
    def callInputs = call_tsvs instanceof List ? call_tsvs : [call_tsvs]
    def detectInputs = detect_status_jsons instanceof List ? detect_status_jsons : [detect_status_jsons]
    def finalizeInputs = finalize_status_jsons instanceof List ? finalize_status_jsons : [finalize_status_jsons]
    assert batchIdInputs.size() == normalizedInputs.size()
    assert batchIdInputs.size() == translatedInputs.size()
    def assembleBatchViews = batchIdInputs.indices.collect { idx ->
        def batchId = batchIdInputs[idx]
        def normalizedDir = normalizedInputs[idx]
        def translatedDir = translatedInputs[idx]
        """
        mkdir -p "status_batch_views/${batchId}"
        ln '${normalizedDir}/download_stage_status.json' "status_batch_views/${batchId}/download_stage_status.json" || cp '${normalizedDir}/download_stage_status.json' "status_batch_views/${batchId}/download_stage_status.json"
        ln '${normalizedDir}/normalize_stage_status.json' "status_batch_views/${batchId}/normalize_stage_status.json" || cp '${normalizedDir}/normalize_stage_status.json' "status_batch_views/${batchId}/normalize_stage_status.json"
        ln '${normalizedDir}/download_manifest.tsv' "status_batch_views/${batchId}/download_manifest.tsv" || cp '${normalizedDir}/download_manifest.tsv' "status_batch_views/${batchId}/download_manifest.tsv"
        ln '${normalizedDir}/genomes.tsv' "status_batch_views/${batchId}/genomes.tsv" || cp '${normalizedDir}/genomes.tsv' "status_batch_views/${batchId}/genomes.tsv"
        ln '${normalizedDir}/sequences.tsv' "status_batch_views/${batchId}/sequences.tsv" || cp '${normalizedDir}/sequences.tsv' "status_batch_views/${batchId}/sequences.tsv"
        ln '${translatedDir}/translate_stage_status.json' "status_batch_views/${batchId}/translate_stage_status.json" || cp '${translatedDir}/translate_stage_status.json' "status_batch_views/${batchId}/translate_stage_status.json"
        ln '${translatedDir}/proteins.tsv' "status_batch_views/${batchId}/proteins.tsv" || cp '${translatedDir}/proteins.tsv' "status_batch_views/${batchId}/proteins.tsv"
        """
    }.join('\n')
    def batchArgs = batchIdInputs.collect { "--batch-dir 'status_batch_views/${it}'" }.join(' ')
    def callArgs = callInputs.collect { "--call-tsv '${it}'" }.join(' ')
    def detectArgs = detectInputs.collect { "--detect-status-json '${it}'" }.join(' ')
    def finalizeArgs = finalizeInputs.collect { "--finalize-status-json '${it}'" }.join(' ')
    """
    mkdir -p status_batch_views
    ${assembleBatchViews}

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

workflow BUILD_ACCESSION_STATUS {
    take:
    batch_table
    batch_inputs
    call_tsvs
    detect_status_jsons
    finalize_status_jsons

    main:
    collectedCallTsvs = call_tsvs.collect()
    collectedDetectStatusJsons = detect_status_jsons.collect()
    collectedFinalizeStatusJsons = finalize_status_jsons.collect()
    statusBuild = BUILD_ACCESSION_STATUS_TASK(
        batch_table,
        batch_inputs,
        collectedCallTsvs,
        collectedDetectStatusJsons,
        collectedFinalizeStatusJsons,
    )

    emit:
    accession_status_tsv = statusBuild.accession_status_tsv
    accession_call_counts_tsv = statusBuild.accession_call_counts_tsv
    status_summary_json = statusBuild.status_summary_json
}
