nextflow.enable.dsl = 2

include { ACQUISITION_FROM_ACCESSIONS } from './workflows/acquisition_from_accessions'
include { DETECTION_FROM_ACQUISITION } from './workflows/detection_from_acquisition'
include { DATABASE_REPORTING } from './workflows/database_reporting'
include { BUILD_ACCESSION_STATUS } from './modules/local/reporting/build_accession_status'

workflow {
  acquisition = ACQUISITION_FROM_ACCESSIONS()
  detection = DETECTION_FROM_ACQUISITION(
    acquisition.batch_rows,
  )
  statusBuild = BUILD_ACCESSION_STATUS(
    acquisition.batch_table,
    acquisition.batch_rows.map { rows -> rows.collect { row -> row[1] } },
    detection.call_tsvs,
    detection.detect_status_jsons,
    detection.finalize_status_jsons,
  )
  reporting = DATABASE_REPORTING(
    acquisition.taxonomy_tsv,
    acquisition.genomes_tsv,
    acquisition.sequences_tsv,
    acquisition.proteins_tsv,
    detection.call_tsvs,
    detection.run_params_tsvs,
  )

  emit:
  acquisition_validation = acquisition.acquisition_validation
  repeat_calls = reporting.repeat_calls
  run_params = reporting.run_params
  sqlite = reporting.sqlite
  sqlite_validation = reporting.sqlite_validation
  summary_by_taxon = reporting.summary_by_taxon
  regression_input = reporting.regression_input
  echarts_report = reporting.echarts_report
  accession_status = statusBuild.accession_status_tsv
  accession_call_counts = statusBuild.accession_call_counts_tsv
  status_summary = statusBuild.status_summary_json
}

workflow.onComplete {
  HomorepeatRuntimeArtifacts.finalizeRun(
    repoRoot: projectDir,
    launchDir: workflow.launchDir,
    runId: params.run_id,
    runRoot: params.run_root,
    publishRoot: params.output_dir,
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
  )
}
