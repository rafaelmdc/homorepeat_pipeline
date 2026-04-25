process EXPORT_PUBLISH_TABLES_TASK {
    label 'reporting'

    input:
    path(batch_table)
    tuple val(batch_ids), path(normalized_batch_dirs, stageAs: 'normalized_batch??'), path(translated_batch_dirs, stageAs: 'translated_batch??')
    path(repeat_calls_tsv)
    path(accession_status_tsv)
    path(accession_call_counts_tsv)
    path(status_summary_json)

    output:
    path('genomes.tsv'), emit: genomes_tsv
    path('taxonomy.tsv'), emit: taxonomy_tsv
    path('matched_sequences.tsv'), emit: matched_sequences_tsv
    path('matched_proteins.tsv'), emit: matched_proteins_tsv
    path('download_manifest.tsv'), emit: download_manifest_tsv
    path('normalization_warnings.tsv'), emit: normalization_warnings_tsv
    path('accession_status.tsv'), emit: accession_status_tsv
    path('accession_call_counts.tsv'), emit: accession_call_counts_tsv
    path('status_summary.json'), emit: status_summary_json
    path('acquisition_validation.json'), emit: acquisition_validation_json

    script:
    def batchIdInputs = batch_ids instanceof List ? batch_ids : [batch_ids]
    def normalizedInputs = normalized_batch_dirs instanceof List ? normalized_batch_dirs : [normalized_batch_dirs]
    def translatedInputs = translated_batch_dirs instanceof List ? translated_batch_dirs : [translated_batch_dirs]
    assert batchIdInputs.size() == normalizedInputs.size()
    assert batchIdInputs.size() == translatedInputs.size()
    def assembleBatchViews = batchIdInputs.indices.collect { idx ->
        def batchId = batchIdInputs[idx]
        def normalizedDir = normalizedInputs[idx]
        def translatedDir = translatedInputs[idx]
        """
        mkdir -p "publish_batch_views/${batchId}"
        cp '${normalizedDir}/genomes.tsv' "publish_batch_views/${batchId}/genomes.tsv"
        cp '${normalizedDir}/taxonomy.tsv' "publish_batch_views/${batchId}/taxonomy.tsv"
        cp '${normalizedDir}/sequences.tsv' "publish_batch_views/${batchId}/sequences.tsv"
        cp '${translatedDir}/proteins.tsv' "publish_batch_views/${batchId}/proteins.tsv"
        cp '${translatedDir}/download_manifest.tsv' "publish_batch_views/${batchId}/download_manifest.tsv"
        cp '${translatedDir}/normalization_warnings.tsv' "publish_batch_views/${batchId}/normalization_warnings.tsv"
        cp '${translatedDir}/acquisition_validation.json' "publish_batch_views/${batchId}/acquisition_validation.json"
        """
    }.join('\n')
    def batchArgs = batchIdInputs.collect { "--batch-dir 'publish_batch_views/${it}'" }.join(' ')
    """
    mkdir -p publish_batch_views
    ${assembleBatchViews}

    ${params.python_bin} -m homorepeat.cli.export_publish_tables \
      --batch-table ${batch_table} \
      ${batchArgs} \
      --repeat-calls-tsv ${repeat_calls_tsv} \
      --accession-status-tsv ${accession_status_tsv} \
      --accession-call-counts-tsv ${accession_call_counts_tsv} \
      --status-summary-json ${status_summary_json} \
      --outdir export_publish_tables_tmp

    mv export_publish_tables_tmp/tables/genomes.tsv genomes.tsv
    mv export_publish_tables_tmp/tables/taxonomy.tsv taxonomy.tsv
    mv export_publish_tables_tmp/tables/matched_sequences.tsv matched_sequences.tsv
    mv export_publish_tables_tmp/tables/matched_proteins.tsv matched_proteins.tsv
    mv export_publish_tables_tmp/tables/download_manifest.tsv download_manifest.tsv
    mv export_publish_tables_tmp/tables/normalization_warnings.tsv normalization_warnings.tsv
    mv export_publish_tables_tmp/tables/accession_status.tsv accession_status.tsv
    mv export_publish_tables_tmp/tables/accession_call_counts.tsv accession_call_counts.tsv
    mv export_publish_tables_tmp/summaries/status_summary.json status_summary.json
    mv export_publish_tables_tmp/summaries/acquisition_validation.json acquisition_validation.json
    """
}

workflow EXPORT_PUBLISH_TABLES {
    take:
    batch_table
    batch_inputs
    repeat_calls_tsv
    accession_status_tsv
    accession_call_counts_tsv
    status_summary_json

    main:
    exports = EXPORT_PUBLISH_TABLES_TASK(
        batch_table,
        batch_inputs,
        repeat_calls_tsv,
        accession_status_tsv,
        accession_call_counts_tsv,
        status_summary_json,
    )

    emit:
    genomes_tsv = exports.genomes_tsv
    taxonomy_tsv = exports.taxonomy_tsv
    matched_sequences_tsv = exports.matched_sequences_tsv
    matched_proteins_tsv = exports.matched_proteins_tsv
    download_manifest_tsv = exports.download_manifest_tsv
    normalization_warnings_tsv = exports.normalization_warnings_tsv
    accession_status_tsv = exports.accession_status_tsv
    accession_call_counts_tsv = exports.accession_call_counts_tsv
    status_summary_json = exports.status_summary_json
    acquisition_validation_json = exports.acquisition_validation_json
}
