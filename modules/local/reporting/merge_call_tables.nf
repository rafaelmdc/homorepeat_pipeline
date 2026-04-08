process MERGE_CALL_TABLES_TASK {
    label 'reporting'

    input:
    path(call_tsvs)
    path(run_params_tsvs)

    output:
    path('repeat_calls.tsv'), emit: repeat_calls_tsv
    path('run_params.tsv'), emit: run_params_tsv

    script:
    def callInputs = call_tsvs instanceof List ? call_tsvs : [call_tsvs]
    def runParamInputs = run_params_tsvs instanceof List ? run_params_tsvs : [run_params_tsvs]
    def callArgs = callInputs.collect { "--call-tsv '${it}'" }.join(' ')
    def runParamArgs = runParamInputs.collect { "--run-params-tsv '${it}'" }.join(' ')
    """
    ${params.python_bin} -m homorepeat.cli.merge_call_tables \
      ${callArgs} \
      ${runParamArgs} \
      --outdir merged_calls_tmp

    mv merged_calls_tmp/repeat_calls.tsv repeat_calls.tsv
    mv merged_calls_tmp/run_params.tsv run_params.tsv
    """
}

workflow MERGE_CALL_TABLES {
    take:
    call_tsvs
    run_params_tsvs

    main:
    collectedCallTsvs = call_tsvs.collect()
    collectedRunParamTsvs = run_params_tsvs.collect()
    merged = MERGE_CALL_TABLES_TASK(collectedCallTsvs, collectedRunParamTsvs)

    emit:
    repeat_calls_tsv = merged.repeat_calls_tsv
    run_params_tsv = merged.run_params_tsv
}
