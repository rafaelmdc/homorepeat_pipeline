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
    dry_run_inputs          : params.dry_run_inputs,
    repeat_residues         : params.repeat_residues,
    taxonomy_auto_build     : params.taxonomy_auto_build,
    taxonomy_cache_dir      : params.taxonomy_cache_dir,
    taxonomy_db_supplied    : params.taxonomy_db_supplied,
    run_pure                : params.run_pure,
    run_threshold           : params.run_threshold,
    run_seed_extend         : params.run_seed_extend,
  ]
}

def validateRepeatResidues = {
  def repeatResidues = params.repeat_residues
    .toString()
    .split(',')
    .collect { it.trim().toUpperCase() }
    .findAll { it }
    .unique()

  if( repeatResidues.isEmpty() ) {
    error "params.repeat_residues must contain at least one standard one-letter amino-acid code, for example Q or Q,N"
  }
  def validResidues = ['A', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'V', 'W', 'Y'] as Set
  def invalidResidues = repeatResidues.findAll { residue -> residue.size() != 1 || !validResidues.contains(residue) }
  if( invalidResidues ) {
    error "params.repeat_residues contains invalid residue code(s): ${invalidResidues.join(',')}. Use comma-separated standard one-letter amino-acid codes, for example Q,N."
  }
  repeatResidues
}

def validateDryRunInputs = { acquisitionPublishMode ->
  if( !params.accessions_file ) {
    error "params.accessions_file is required. Provide a text file with one NCBI assembly accession per line, for example --accessions_file examples/accessions/smoke_human.txt"
  }
  if( !params.taxonomy_db ) {
    error "params.taxonomy_db is required"
  }
  if( !params.run_pure && !params.run_threshold && !params.run_seed_extend ) {
    error "At least one detection path must be enabled"
  }

  def accessionsFile = file(params.accessions_file)
  if( !accessionsFile.exists() ) {
    error "accessions file not found: ${params.accessions_file}. Provide a text file with one NCBI assembly accession per line."
  }
  def requestedAccessions = accessionsFile.toFile().readLines('UTF-8')
    .collect { it.trim() }
    .findAll { it && !it.startsWith('#') }
  if( requestedAccessions.isEmpty() ) {
    error "accessions file has no usable accession lines: ${params.accessions_file}. Add one NCBI assembly accession per non-comment line, for example GCF_000001405.40."
  }

  def requestedTaxonomyDb = file(params.taxonomy_db)
  def taxonomyDbSupplied = params.taxonomy_db_supplied.toString().toBoolean()
  def taxonomyAutoBuild = params.taxonomy_auto_build.toString().toBoolean()
  def taxonomyStatus = requestedTaxonomyDb.exists() ? "exists" : "will_auto_build"
  if( !requestedTaxonomyDb.exists() && (taxonomyDbSupplied || !taxonomyAutoBuild) ) {
    error "taxonomy database not found: ${params.taxonomy_db}. Use an existing file with --taxonomy_db, or omit --taxonomy_db so the default cache can be built automatically."
  }

  def repeatResidues = validateRepeatResidues()
  [
    "HomoRepeat input dry run passed.",
    "Accessions file: ${params.accessions_file}",
    "Usable accessions: ${requestedAccessions.size()}",
    "Repeat residues: ${repeatResidues.join(',')}",
    "Acquisition publish mode: ${acquisitionPublishMode}",
    "Taxonomy DB: ${params.taxonomy_db} (${taxonomyStatus})",
  ].join('\n')
}

workflow {
  def acquisitionPublishMode = normalizedAcquisitionPublishMode()
  def callsRepeatCh = Channel.empty()
  def callsParamsCh = Channel.empty()
  def databaseSqliteCh = Channel.empty()
  def databaseSqliteValidationCh = Channel.empty()
  def reportsSummaryByTaxonCh = Channel.empty()
  def reportsRegressionInputCh = Channel.empty()
  def reportsEchartsOptionsCh = Channel.empty()
  def reportsEchartsHtmlCh = Channel.empty()
  def reportsEchartsJsCh = Channel.empty()
  def tablesGenomesCh = Channel.empty()
  def tablesTaxonomyCh = Channel.empty()
  def tablesMatchedSequencesCh = Channel.empty()
  def tablesMatchedProteinsCh = Channel.empty()
  def tablesRepeatCallCodonUsageCh = Channel.empty()
  def tablesRepeatContextCh = Channel.empty()
  def tablesDownloadManifestCh = Channel.empty()
  def tablesNormalizationWarningsCh = Channel.empty()
  def tablesAccessionStatusCh = Channel.empty()
  def tablesAccessionCallCountsCh = Channel.empty()
  def summariesStatusCh = Channel.empty()
  def summariesAcquisitionValidationCh = Channel.empty()

  if( params.dry_run_inputs.toString().toBoolean() ) {
    log.info validateDryRunInputs(acquisitionPublishMode)
  } else {
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
    callsRepeatCh = canonicalCalls.repeat_calls_tsv
    callsParamsCh = canonicalCalls.run_params_tsv
    tablesGenomesCh = flatPublishTables.genomes_tsv
    tablesTaxonomyCh = flatPublishTables.taxonomy_tsv
    tablesMatchedSequencesCh = flatPublishTables.matched_sequences_tsv
    tablesMatchedProteinsCh = flatPublishTables.matched_proteins_tsv
    tablesRepeatCallCodonUsageCh = canonicalCodonUsage.repeat_call_codon_usage_tsv
    tablesRepeatContextCh = repeatContext.repeat_context_tsv
    tablesDownloadManifestCh = flatPublishTables.download_manifest_tsv
    tablesNormalizationWarningsCh = flatPublishTables.normalization_warnings_tsv
    tablesAccessionStatusCh = flatPublishTables.accession_status_tsv
    tablesAccessionCallCountsCh = flatPublishTables.accession_call_counts_tsv
    summariesStatusCh = flatPublishTables.status_summary_json
    summariesAcquisitionValidationCh = flatPublishTables.acquisition_validation_json

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
  }

  publish:
  calls_repeat = callsRepeatCh.ifEmpty([])
  calls_params = callsParamsCh.ifEmpty([])
  database_sqlite = databaseSqliteCh
  database_sqlite_validation = databaseSqliteValidationCh
  reports_summary_by_taxon = reportsSummaryByTaxonCh
  reports_regression_input = reportsRegressionInputCh
  reports_echarts_options = reportsEchartsOptionsCh
  reports_echarts_html = reportsEchartsHtmlCh
  reports_echarts_js = reportsEchartsJsCh
  tables_genomes = tablesGenomesCh.ifEmpty([])
  tables_taxonomy = tablesTaxonomyCh.ifEmpty([])
  tables_matched_sequences = tablesMatchedSequencesCh.ifEmpty([])
  tables_matched_proteins = tablesMatchedProteinsCh.ifEmpty([])
  tables_repeat_call_codon_usage = tablesRepeatCallCodonUsageCh.ifEmpty([])
  tables_repeat_context = tablesRepeatContextCh.ifEmpty([])
  tables_download_manifest = tablesDownloadManifestCh.ifEmpty([])
  tables_normalization_warnings = tablesNormalizationWarningsCh.ifEmpty([])
  tables_accession_status = tablesAccessionStatusCh.ifEmpty([])
  tables_accession_call_counts = tablesAccessionCallCountsCh.ifEmpty([])
  summaries_status = summariesStatusCh.ifEmpty([])
  summaries_acquisition_validation = summariesAcquisitionValidationCh.ifEmpty([])
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
    status: workflow.success ? (params.dry_run_inputs.toString().toBoolean() ? 'dry_run_success' : 'success') : 'failed',
    success: workflow.success,
    dryRunInputs: params.dry_run_inputs.toString().toBoolean(),
    runName: workflow.runName,
    workDir: workflow.workDir,
    acquisitionPublishMode: normalizedAcquisitionPublishMode(),
    effectiveParams: effectiveManifestParams(normalizedAcquisitionPublishMode()),
  )
}
