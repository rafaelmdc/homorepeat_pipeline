nextflow.enable.dsl = 2

include { ACQUISITION_FROM_ACCESSIONS } from './workflows/acquisition_from_accessions'
include { DETECTION_FROM_ACQUISITION } from './workflows/detection_from_acquisition'
include { DATABASE_REPORTING } from './workflows/database_reporting'
include { BUILD_ACCESSION_STATUS } from './modules/local/reporting/build_accession_status'
include { EXPORT_REPEAT_CONTEXT } from './modules/local/reporting/export_repeat_context'
include { EXPORT_PUBLISH_TABLES } from './modules/local/reporting/export_publish_tables'
include { MERGE_CALL_TABLES } from './modules/local/reporting/merge_call_tables'
include { MERGE_CODON_USAGE_TABLES } from './modules/local/reporting/merge_codon_usage_tables'

def normalizedAcquisitionPublishMode = {
  def mode = (params.acquisition_publish_mode ?: 'raw').toString().trim().toLowerCase()
  if( !['raw', 'merged'].contains(mode) ) {
    error "params.acquisition_publish_mode must be one of: raw, merged"
  }
  mode
}

def effectiveManifestParams = { acquisitionPublishMode ->
  [
    acquisition_publish_mode: acquisitionPublishMode,
    batch_size              : params.batch_size,
    repeat_residues         : params.repeat_residues,
    run_pure                : params.run_pure,
    run_threshold           : params.run_threshold,
    run_seed_extend         : params.run_seed_extend,
  ]
}

workflow {
  def acquisitionPublishMode = normalizedAcquisitionPublishMode()
  acquisition = ACQUISITION_FROM_ACCESSIONS()
  detection = DETECTION_FROM_ACQUISITION(
    acquisition.batch_rows,
  )
  statusBuild = BUILD_ACCESSION_STATUS(
    acquisition.batch_table,
    acquisition.batch_inputs,
    detection.call_tsvs,
    detection.detect_status_jsons,
    detection.finalize_status_jsons,
  )
  canonicalCalls = MERGE_CALL_TABLES(
    detection.call_tsvs,
    detection.run_params_tsvs,
  )
  canonicalCodonUsage = MERGE_CODON_USAGE_TABLES(
    detection.codon_usage_tsvs,
  )
  repeatContext = EXPORT_REPEAT_CONTEXT(
    acquisition.batch_inputs,
    canonicalCalls.repeat_calls_tsv,
  )
  flatPublishTables = EXPORT_PUBLISH_TABLES(
    acquisition.batch_table,
    acquisition.batch_inputs,
    canonicalCalls.repeat_calls_tsv,
    statusBuild.accession_status_tsv,
    statusBuild.accession_call_counts_tsv,
    statusBuild.status_summary_json,
  )
  def databaseSqliteCh = Channel.empty()
  def databaseSqliteValidationCh = Channel.empty()
  def reportsSummaryByTaxonCh = Channel.empty()
  def reportsRegressionInputCh = Channel.empty()
  def reportsEchartsOptionsCh = Channel.empty()
  def reportsEchartsHtmlCh = Channel.empty()
  def reportsEchartsJsCh = Channel.empty()

  if( acquisitionPublishMode == 'merged' ) {
    reporting = DATABASE_REPORTING(
      acquisition.taxonomy_tsv,
      acquisition.genomes_tsv,
      acquisition.sequences_tsv,
      acquisition.proteins_tsv,
      canonicalCalls.repeat_calls_tsv,
      canonicalCalls.run_params_tsv,
    )
    databaseSqliteCh = reporting.sqlite
    databaseSqliteValidationCh = reporting.sqlite_validation
    reportsSummaryByTaxonCh = reporting.summary_by_taxon
    reportsRegressionInputCh = reporting.regression_input
    reportsEchartsOptionsCh = reporting.echarts_options
    reportsEchartsHtmlCh = reporting.echarts_report
    reportsEchartsJsCh = reporting.echarts_js
  }

  publish:
  calls_repeat = canonicalCalls.repeat_calls_tsv.ifEmpty([])
  calls_params = canonicalCalls.run_params_tsv.ifEmpty([])
  database_sqlite = databaseSqliteCh.ifEmpty([])
  database_sqlite_validation = databaseSqliteValidationCh.ifEmpty([])
  reports_summary_by_taxon = reportsSummaryByTaxonCh.ifEmpty([])
  reports_regression_input = reportsRegressionInputCh.ifEmpty([])
  reports_echarts_options = reportsEchartsOptionsCh.ifEmpty([])
  reports_echarts_html = reportsEchartsHtmlCh.ifEmpty([])
  reports_echarts_js = reportsEchartsJsCh.ifEmpty([])
  tables_genomes = flatPublishTables.genomes_tsv.ifEmpty([])
  tables_taxonomy = flatPublishTables.taxonomy_tsv.ifEmpty([])
  tables_matched_sequences = flatPublishTables.matched_sequences_tsv.ifEmpty([])
  tables_matched_proteins = flatPublishTables.matched_proteins_tsv.ifEmpty([])
  tables_repeat_call_codon_usage = canonicalCodonUsage.repeat_call_codon_usage_tsv.ifEmpty([])
  tables_repeat_context = repeatContext.repeat_context_tsv.ifEmpty([])
  tables_download_manifest = flatPublishTables.download_manifest_tsv.ifEmpty([])
  tables_normalization_warnings = flatPublishTables.normalization_warnings_tsv.ifEmpty([])
  tables_accession_status = flatPublishTables.accession_status_tsv.ifEmpty([])
  tables_accession_call_counts = flatPublishTables.accession_call_counts_tsv.ifEmpty([])
  summaries_status = flatPublishTables.status_summary_json.ifEmpty([])
  summaries_acquisition_validation = flatPublishTables.acquisition_validation_json.ifEmpty([])

  emit:
  genomes_tsv = acquisition.genomes_tsv
  taxonomy_tsv = acquisition.taxonomy_tsv
  sequences_tsv = acquisition.sequences_tsv
  proteins_tsv = acquisition.proteins_tsv
  cds_fasta = acquisition.cds_fasta
  proteins_fasta = acquisition.proteins_fasta
  download_manifest_tsv = acquisition.download_manifest_tsv
  normalization_warnings_tsv = acquisition.normalization_warnings_tsv
  acquisition_validation = acquisition.acquisition_validation
  finalized_dirs = detection.finalized_dirs
  repeat_calls = canonicalCalls.repeat_calls_tsv
  run_params = canonicalCalls.run_params_tsv
  sqlite = databaseSqliteCh
  sqlite_validation = databaseSqliteValidationCh
  summary_by_taxon = reportsSummaryByTaxonCh
  regression_input = reportsRegressionInputCh
  echarts_options = reportsEchartsOptionsCh
  echarts_report = reportsEchartsHtmlCh
  echarts_js = reportsEchartsJsCh
  accession_status = statusBuild.accession_status_tsv
  accession_call_counts = statusBuild.accession_call_counts_tsv
  status_summary = statusBuild.status_summary_json
  tables_genomes_tsv = flatPublishTables.genomes_tsv
  tables_taxonomy_tsv = flatPublishTables.taxonomy_tsv
  tables_matched_sequences_tsv = flatPublishTables.matched_sequences_tsv
  tables_matched_proteins_tsv = flatPublishTables.matched_proteins_tsv
  tables_repeat_call_codon_usage_tsv = canonicalCodonUsage.repeat_call_codon_usage_tsv
  tables_repeat_context_tsv = repeatContext.repeat_context_tsv
  tables_download_manifest_tsv = flatPublishTables.download_manifest_tsv
  tables_normalization_warnings_tsv = flatPublishTables.normalization_warnings_tsv
  tables_accession_status_tsv = flatPublishTables.accession_status_tsv
  tables_accession_call_counts_tsv = flatPublishTables.accession_call_counts_tsv
  summaries_status_summary_json = flatPublishTables.status_summary_json
  summaries_acquisition_validation_json = flatPublishTables.acquisition_validation_json
}

output {
  calls_repeat {
    path 'calls'
  }
  calls_params {
    path 'calls'
  }
  database_sqlite {
    path 'database'
  }
  database_sqlite_validation {
    path 'database'
  }
  reports_summary_by_taxon {
    path 'reports'
  }
  reports_regression_input {
    path 'reports'
  }
  reports_echarts_options {
    path 'reports'
  }
  reports_echarts_html {
    path 'reports'
  }
  reports_echarts_js {
    path 'reports'
  }
  tables_genomes {
    path 'tables'
  }
  tables_taxonomy {
    path 'tables'
  }
  tables_matched_sequences {
    path 'tables'
  }
  tables_matched_proteins {
    path 'tables'
  }
  tables_repeat_call_codon_usage {
    path 'tables'
  }
  tables_repeat_context {
    path 'tables'
  }
  tables_download_manifest {
    path 'tables'
  }
  tables_normalization_warnings {
    path 'tables'
  }
  tables_accession_status {
    path 'tables'
  }
  tables_accession_call_counts {
    path 'tables'
  }
  summaries_status {
    path 'summaries'
  }
  summaries_acquisition_validation {
    path 'summaries'
  }
}

workflow.onComplete {
  HomorepeatRuntimeArtifacts.finalizeRun(
    repoRoot: projectDir,
    launchDir: workflow.launchDir,
    runId: params.run_id,
    runRoot: params.run_root,
    publishRoot: workflow.outputDir,
    accessionsFile: params.accessions_file,
    taxonomyDb: params.taxonomy_db,
    profile: workflow.profile,
    commandLine: workflow.commandLine,
    startedAt: workflow.start,
    finishedAt: workflow.complete,
    status: workflow.success ? 'success' : 'failed',
    success: workflow.success,
    runName: workflow.runName,
    workDir: workflow.workDir,
    acquisitionPublishMode: normalizedAcquisitionPublishMode(),
    effectiveParams: effectiveManifestParams(normalizedAcquisitionPublishMode()),
  )
}
