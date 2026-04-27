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
    taxonomy_auto_build     : params.taxonomy_auto_build,
    taxonomy_cache_dir      : params.taxonomy_cache_dir,
    taxonomy_db_supplied    : params.taxonomy_db_supplied,
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
  database_sqlite = databaseSqliteCh
  database_sqlite_validation = databaseSqliteValidationCh
  reports_summary_by_taxon = reportsSummaryByTaxonCh
  reports_regression_input = reportsRegressionInputCh
  reports_echarts_options = reportsEchartsOptionsCh
  reports_echarts_html = reportsEchartsHtmlCh
  reports_echarts_js = reportsEchartsJsCh
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
}

output {
  calls_repeat {
    path 'calls'
  }
  calls_params {
    path 'calls'
  }
  database_sqlite {
    enabled normalizedAcquisitionPublishMode() == 'merged'
    path 'database'
  }
  database_sqlite_validation {
    enabled normalizedAcquisitionPublishMode() == 'merged'
    path 'database'
  }
  reports_summary_by_taxon {
    enabled normalizedAcquisitionPublishMode() == 'merged'
    path 'reports'
  }
  reports_regression_input {
    enabled normalizedAcquisitionPublishMode() == 'merged'
    path 'reports'
  }
  reports_echarts_options {
    enabled normalizedAcquisitionPublishMode() == 'merged'
    path 'reports'
  }
  reports_echarts_html {
    enabled normalizedAcquisitionPublishMode() == 'merged'
    path 'reports'
  }
  reports_echarts_js {
    enabled normalizedAcquisitionPublishMode() == 'merged'
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
