process PREPARE_REPORT_TABLES {
    label 'reporting'
    publishDir "${params.output_dir}/reports", mode: 'copy'

    input:
    path(summary_tsv)
    path(regression_tsv)

    output:
    path('echarts_options.json'), emit: echarts_options

    script:
    """
    ${params.python_bin} -m homorepeat.cli.prepare_report_tables \
      --summary-tsv ${summary_tsv} \
      --regression-tsv ${regression_tsv} \
      --outdir reports_tmp

    mv reports_tmp/echarts_options.json echarts_options.json
    """
}
