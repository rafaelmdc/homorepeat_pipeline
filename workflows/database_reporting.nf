nextflow.enable.dsl = 2

include { BUILD_SQLITE } from '../modules/local/reporting/build_sqlite'
include { EXPORT_SUMMARY_TABLES } from '../modules/local/reporting/export_summary_tables'
include { MERGE_CALL_TABLES } from '../modules/local/reporting/merge_call_tables'
include { PREPARE_REPORT_TABLES } from '../modules/local/reporting/prepare_report_tables'
include { RENDER_ECHARTS_REPORT } from '../modules/local/reporting/render_echarts_report'

workflow DATABASE_REPORTING {
    take:
    taxonomy_tsv
    genomes_tsv
    sequences_tsv
    proteins_tsv
    call_tsv
    run_params_tsv

    main:
    canonicalCalls = MERGE_CALL_TABLES(call_tsv.collect(), run_params_tsv.collect())
    sqliteBuild = BUILD_SQLITE(
        taxonomy_tsv,
        genomes_tsv,
        sequences_tsv,
        proteins_tsv,
        canonicalCalls.repeat_calls_tsv,
        canonicalCalls.run_params_tsv,
    )
    summaries = EXPORT_SUMMARY_TABLES(taxonomy_tsv, proteins_tsv, canonicalCalls.repeat_calls_tsv)
    reportPrep = PREPARE_REPORT_TABLES(summaries.summary_tsv, summaries.regression_tsv)
    reportHtml = RENDER_ECHARTS_REPORT(summaries.summary_tsv, summaries.regression_tsv, reportPrep.echarts_options)

    emit:
    repeat_calls = canonicalCalls.repeat_calls_tsv
    run_params = canonicalCalls.run_params_tsv
    sqlite = sqliteBuild.sqlite_db
    sqlite_validation = sqliteBuild.sqlite_validation
    summary_by_taxon = summaries.summary_tsv
    regression_input = summaries.regression_tsv
    echarts_report = reportHtml.echarts_report
}
