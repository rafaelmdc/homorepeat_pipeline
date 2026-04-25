process EXPORT_REPEAT_CONTEXT_TASK {
    label 'reporting'

    input:
    tuple val(batch_ids), path(normalized_batch_dirs, stageAs: 'normalized_batch??'), path(translated_batch_dirs, stageAs: 'translated_batch??')
    path(repeat_calls_tsv)

    output:
    path('repeat_context.tsv'), emit: repeat_context_tsv

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
        mkdir -p "repeat_context_batch_views/${batchId}"
        cp '${normalizedDir}/cds.fna' "repeat_context_batch_views/${batchId}/cds.fna"
        cp '${translatedDir}/proteins.faa' "repeat_context_batch_views/${batchId}/proteins.faa"
        """
    }.join('\n')
    def batchArgs = batchIdInputs.collect { "--batch-dir 'repeat_context_batch_views/${it}'" }.join(' ')
    """
    mkdir -p repeat_context_batch_views
    ${assembleBatchViews}

    ${params.python_bin} -m homorepeat.cli.export_repeat_context \
      --repeat-calls-tsv ${repeat_calls_tsv} \
      ${batchArgs} \
      --outdir repeat_context_tmp

    mv repeat_context_tmp/repeat_context.tsv repeat_context.tsv
    """
}

workflow EXPORT_REPEAT_CONTEXT {
    take:
    batch_inputs
    repeat_calls_tsv

    main:
    context = EXPORT_REPEAT_CONTEXT_TASK(
        batch_inputs,
        repeat_calls_tsv,
    )

    emit:
    repeat_context_tsv = context.repeat_context_tsv
}
