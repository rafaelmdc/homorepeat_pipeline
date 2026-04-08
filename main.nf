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

  publish:
  acquisition_genomes = acquisition.genomes_tsv
  acquisition_taxonomy = acquisition.taxonomy_tsv
  acquisition_sequences = acquisition.sequences_tsv
  acquisition_proteins = acquisition.proteins_tsv
  acquisition_cds = acquisition.cds_fasta
  acquisition_proteins_fasta = acquisition.proteins_fasta
  acquisition_download_manifest = acquisition.download_manifest_tsv
  acquisition_normalization_warnings = acquisition.normalization_warnings_tsv
  acquisition_validation = acquisition.acquisition_validation
  calls_repeat = reporting.repeat_calls
  calls_params = reporting.run_params
  calls_finalized = detection.finalized_dirs
  database_sqlite = reporting.sqlite
  database_sqlite_validation = reporting.sqlite_validation
  reports_summary_by_taxon = reporting.summary_by_taxon
  reports_regression_input = reporting.regression_input
  reports_echarts_options = reporting.echarts_options
  reports_echarts_html = reporting.echarts_report
  reports_echarts_js = reporting.echarts_js
  status_accession = statusBuild.accession_status_tsv
  status_accession_call_counts = statusBuild.accession_call_counts_tsv
  status_summary = statusBuild.status_summary_json

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
  repeat_calls = reporting.repeat_calls
  run_params = reporting.run_params
  sqlite = reporting.sqlite
  sqlite_validation = reporting.sqlite_validation
  summary_by_taxon = reporting.summary_by_taxon
  regression_input = reporting.regression_input
  echarts_options = reporting.echarts_options
  echarts_report = reporting.echarts_report
  echarts_js = reporting.echarts_js
  accession_status = statusBuild.accession_status_tsv
  accession_call_counts = statusBuild.accession_call_counts_tsv
  status_summary = statusBuild.status_summary_json
}

output {
  acquisition_genomes { path 'acquisition' }
  acquisition_taxonomy { path 'acquisition' }
  acquisition_sequences { path 'acquisition' }
  acquisition_proteins { path 'acquisition' }
  acquisition_cds { path 'acquisition' }
  acquisition_proteins_fasta { path 'acquisition' }
  acquisition_download_manifest { path 'acquisition' }
  acquisition_normalization_warnings { path 'acquisition' }
  acquisition_validation { path 'acquisition' }
  calls_repeat { path 'calls' }
  calls_params { path 'calls' }
  calls_finalized {
    path { batchId, method, repeatResidue, finalizedDir -> "calls/finalized/${method}/${repeatResidue}" }
  }
  database_sqlite { path 'database' }
  database_sqlite_validation { path 'database' }
  reports_summary_by_taxon { path 'reports' }
  reports_regression_input { path 'reports' }
  reports_echarts_options { path 'reports' }
  reports_echarts_html { path 'reports' }
  reports_echarts_js { path 'reports' }
  status_accession { path 'status' }
  status_accession_call_counts { path 'status' }
  status_summary { path 'status' }
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
  )
}
