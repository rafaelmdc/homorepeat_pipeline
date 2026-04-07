process EXPORT_SUMMARY_TABLES {
    label 'reporting'
    publishDir "${params.output_dir}/reports", mode: 'copy'

    input:
    path(taxonomy_tsv)
    path(proteins_tsv)
    path(call_tsvs)

    output:
    path('summary_by_taxon.tsv'), emit: summary_tsv
    path('regression_input.tsv'), emit: regression_tsv

    script:
    def callInputs = call_tsvs instanceof List ? call_tsvs : [call_tsvs]
    def callArgs = callInputs.collect { "--call-tsv '${it}'" }.join(' ')
    """
    ${params.python_bin} -m homorepeat.cli.export_summary_tables \
      --taxonomy-tsv ${taxonomy_tsv} \
      --proteins-tsv ${proteins_tsv} \
      ${callArgs} \
      --outdir reports_tmp

    mv reports_tmp/summary_by_taxon.tsv summary_by_taxon.tsv
    mv reports_tmp/regression_input.tsv regression_input.tsv
    """
}
