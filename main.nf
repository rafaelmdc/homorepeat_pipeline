nextflow.enable.dsl = 2

include { ACQUISITION_FROM_ACCESSIONS } from './workflows/acquisition_from_accessions'
include { DETECTION_FROM_ACQUISITION } from './workflows/detection_from_acquisition'
include { DATABASE_REPORTING } from './workflows/database_reporting'
include { BUILD_ACCESSION_STATUS } from './modules/local/reporting/build_accession_status'
include { EXPORT_PUBLISH_TABLES } from './modules/local/reporting/export_publish_tables'
include { MERGE_CALL_TABLES } from './modules/local/reporting/merge_call_tables'

def WORKFLOW_OUTPUT_PLACEHOLDER_FILE = file(
  "${projectDir}/runtime/output_placeholders/workflow_output_placeholder.txt",
  checkIfExists: true,
)
def WORKFLOW_OUTPUT_PLACEHOLDER_DIR = file(
  "${projectDir}/runtime/output_placeholders/finalized_placeholder",
  checkIfExists: true,
)
def WORKFLOW_OUTPUT_PLACEHOLDER_BATCH_ID = '__workflow_output_placeholder__'
def WORKFLOW_OUTPUT_PLACEHOLDER_METHOD = '__workflow_output_placeholder__'
def WORKFLOW_OUTPUT_PLACEHOLDER_RESIDUE = '__workflow_output_placeholder__'

def publishablePathChannel = { channel ->
  channel.mix(Channel.value(WORKFLOW_OUTPUT_PLACEHOLDER_FILE))
}

def publishableFinalizedChannel = { channel ->
  channel.mix(Channel.value(
    tuple(
      WORKFLOW_OUTPUT_PLACEHOLDER_BATCH_ID,
      WORKFLOW_OUTPUT_PLACEHOLDER_METHOD,
      WORKFLOW_OUTPUT_PLACEHOLDER_RESIDUE,
      WORKFLOW_OUTPUT_PLACEHOLDER_DIR,
    )
  ))
}

def publishTarget = { targetDir, artifact ->
  artifact?.toString() == WORKFLOW_OUTPUT_PLACEHOLDER_FILE.getFileName().toString() ||
    artifact?.toString()?.endsWith("/${WORKFLOW_OUTPUT_PLACEHOLDER_FILE.getFileName()}")
    ? ".nf_placeholders/${targetDir}"
    : targetDir
}

def finalizedPublishTarget = { batchId, method, repeatResidue, finalizedDir ->
  batchId == WORKFLOW_OUTPUT_PLACEHOLDER_BATCH_ID
    ? '.nf_placeholders/finalized'
    : "calls/finalized/${method}/${repeatResidue}"
}

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
  acquisition_genomes = publishablePathChannel(acquisition.genomes_tsv)
  acquisition_taxonomy = publishablePathChannel(acquisition.taxonomy_tsv)
  acquisition_sequences = publishablePathChannel(acquisition.sequences_tsv)
  acquisition_proteins = publishablePathChannel(acquisition.proteins_tsv)
  acquisition_cds = publishablePathChannel(acquisition.cds_fasta)
  acquisition_proteins_fasta = publishablePathChannel(acquisition.proteins_fasta)
  acquisition_download_manifest = publishablePathChannel(acquisition.download_manifest_tsv)
  acquisition_normalization_warnings = publishablePathChannel(acquisition.normalization_warnings_tsv)
  acquisition_validation = publishablePathChannel(acquisition.acquisition_validation)
  calls_repeat = publishablePathChannel(canonicalCalls.repeat_calls_tsv)
  calls_params = publishablePathChannel(canonicalCalls.run_params_tsv)
  calls_finalized = publishableFinalizedChannel(detection.finalized_dirs)
  database_sqlite = publishablePathChannel(databaseSqliteCh)
  database_sqlite_validation = publishablePathChannel(databaseSqliteValidationCh)
  reports_summary_by_taxon = publishablePathChannel(reportsSummaryByTaxonCh)
  reports_regression_input = publishablePathChannel(reportsRegressionInputCh)
  reports_echarts_options = publishablePathChannel(reportsEchartsOptionsCh)
  reports_echarts_html = publishablePathChannel(reportsEchartsHtmlCh)
  reports_echarts_js = publishablePathChannel(reportsEchartsJsCh)
  status_accession = publishablePathChannel(statusBuild.accession_status_tsv)
  status_accession_call_counts = publishablePathChannel(statusBuild.accession_call_counts_tsv)
  status_summary = publishablePathChannel(statusBuild.status_summary_json)
  tables_genomes = publishablePathChannel(flatPublishTables.genomes_tsv)
  tables_taxonomy = publishablePathChannel(flatPublishTables.taxonomy_tsv)
  tables_matched_sequences = publishablePathChannel(flatPublishTables.matched_sequences_tsv)
  tables_download_manifest = publishablePathChannel(flatPublishTables.download_manifest_tsv)
  tables_normalization_warnings = publishablePathChannel(flatPublishTables.normalization_warnings_tsv)
  tables_accession_status = publishablePathChannel(flatPublishTables.accession_status_tsv)
  tables_accession_call_counts = publishablePathChannel(flatPublishTables.accession_call_counts_tsv)
  summaries_status = publishablePathChannel(flatPublishTables.status_summary_json)
  summaries_acquisition_validation = publishablePathChannel(flatPublishTables.acquisition_validation_json)

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
  tables_download_manifest_tsv = flatPublishTables.download_manifest_tsv
  tables_normalization_warnings_tsv = flatPublishTables.normalization_warnings_tsv
  tables_accession_status_tsv = flatPublishTables.accession_status_tsv
  tables_accession_call_counts_tsv = flatPublishTables.accession_call_counts_tsv
  summaries_status_summary_json = flatPublishTables.status_summary_json
  summaries_acquisition_validation_json = flatPublishTables.acquisition_validation_json
}

output {
  acquisition_genomes { path { artifact -> publishTarget('acquisition', artifact) } }
  acquisition_taxonomy { path { artifact -> publishTarget('acquisition', artifact) } }
  acquisition_sequences { path { artifact -> publishTarget('acquisition', artifact) } }
  acquisition_proteins { path { artifact -> publishTarget('acquisition', artifact) } }
  acquisition_cds { path { artifact -> publishTarget('acquisition', artifact) } }
  acquisition_proteins_fasta { path { artifact -> publishTarget('acquisition', artifact) } }
  acquisition_download_manifest { path { artifact -> publishTarget('acquisition', artifact) } }
  acquisition_normalization_warnings { path { artifact -> publishTarget('acquisition', artifact) } }
  acquisition_validation { path { artifact -> publishTarget('acquisition', artifact) } }
  calls_repeat { path { artifact -> publishTarget('calls', artifact) } }
  calls_params { path { artifact -> publishTarget('calls', artifact) } }
  calls_finalized {
    path { batchId, method, repeatResidue, finalizedDir ->
      finalizedPublishTarget(batchId, method, repeatResidue, finalizedDir)
    }
  }
  database_sqlite { path { artifact -> publishTarget('database', artifact) } }
  database_sqlite_validation { path { artifact -> publishTarget('database', artifact) } }
  reports_summary_by_taxon { path { artifact -> publishTarget('reports', artifact) } }
  reports_regression_input { path { artifact -> publishTarget('reports', artifact) } }
  reports_echarts_options { path { artifact -> publishTarget('reports', artifact) } }
  reports_echarts_html { path { artifact -> publishTarget('reports', artifact) } }
  reports_echarts_js { path { artifact -> publishTarget('reports', artifact) } }
  status_accession { path { artifact -> publishTarget('status', artifact) } }
  status_accession_call_counts { path { artifact -> publishTarget('status', artifact) } }
  status_summary { path { artifact -> publishTarget('status', artifact) } }
  tables_genomes { path { artifact -> publishTarget('tables', artifact) } }
  tables_taxonomy { path { artifact -> publishTarget('tables', artifact) } }
  tables_matched_sequences { path { artifact -> publishTarget('tables', artifact) } }
  tables_download_manifest { path { artifact -> publishTarget('tables', artifact) } }
  tables_normalization_warnings { path { artifact -> publishTarget('tables', artifact) } }
  tables_accession_status { path { artifact -> publishTarget('tables', artifact) } }
  tables_accession_call_counts { path { artifact -> publishTarget('tables', artifact) } }
  summaries_status { path { artifact -> publishTarget('summaries', artifact) } }
  summaries_acquisition_validation { path { artifact -> publishTarget('summaries', artifact) } }
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
