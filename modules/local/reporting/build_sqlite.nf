process BUILD_SQLITE {
    label 'database'
    publishDir "${params.output_dir}/database/sqlite", mode: 'copy'

    input:
    path(taxonomy_tsv)
    path(genomes_tsv)
    path(sequences_tsv)
    path(proteins_tsv)
    path(call_tsvs)
    path(run_params_tsvs)

    output:
    path('homorepeat.sqlite'), emit: sqlite_db
    path('sqlite_validation.json'), emit: sqlite_validation

    script:
    def callInputs = call_tsvs instanceof List ? call_tsvs : [call_tsvs]
    def runParamInputs = run_params_tsvs instanceof List ? run_params_tsvs : [run_params_tsvs]
    def callArgs = callInputs.collect { "--call-tsv '${it}'" }.join(' ')
    def runParamArgs = runParamInputs.collect { "--run-params-tsv '${it}'" }.join(' ')
    """
    ${params.python_bin} -m homorepeat.cli.build_sqlite \
      --taxonomy-tsv ${taxonomy_tsv} \
      --genomes-tsv ${genomes_tsv} \
      --sequences-tsv ${sequences_tsv} \
      --proteins-tsv ${proteins_tsv} \
      ${callArgs} \
      ${runParamArgs} \
      --outdir sqlite_tmp

    mv sqlite_tmp/homorepeat.sqlite homorepeat.sqlite
    mv sqlite_tmp/sqlite_validation.json sqlite_validation.json
    """
}
