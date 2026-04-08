nextflow.enable.dsl = 2

include { ACQUISITION_FROM_ACCESSIONS } from './workflows/acquisition_from_accessions'
include { DETECTION_FROM_ACQUISITION } from './workflows/detection_from_acquisition'
include { DATABASE_REPORTING } from './workflows/database_reporting'
include { BUILD_ACCESSION_STATUS } from './modules/local/reporting/build_accession_status'

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
  acquisition_genomes = publishablePathChannel(acquisition.genomes_tsv)
  acquisition_taxonomy = publishablePathChannel(acquisition.taxonomy_tsv)
  acquisition_sequences = publishablePathChannel(acquisition.sequences_tsv)
  acquisition_proteins = publishablePathChannel(acquisition.proteins_tsv)
  acquisition_cds = publishablePathChannel(acquisition.cds_fasta)
  acquisition_proteins_fasta = publishablePathChannel(acquisition.proteins_fasta)
  acquisition_download_manifest = publishablePathChannel(acquisition.download_manifest_tsv)
  acquisition_normalization_warnings = publishablePathChannel(acquisition.normalization_warnings_tsv)
  acquisition_validation = publishablePathChannel(acquisition.acquisition_validation)
  calls_repeat = publishablePathChannel(reporting.repeat_calls)
  calls_params = publishablePathChannel(reporting.run_params)
  calls_finalized = publishableFinalizedChannel(detection.finalized_dirs)
  database_sqlite = publishablePathChannel(reporting.sqlite)
  database_sqlite_validation = publishablePathChannel(reporting.sqlite_validation)
  reports_summary_by_taxon = publishablePathChannel(reporting.summary_by_taxon)
  reports_regression_input = publishablePathChannel(reporting.regression_input)
  reports_echarts_options = publishablePathChannel(reporting.echarts_options)
  reports_echarts_html = publishablePathChannel(reporting.echarts_report)
  reports_echarts_js = publishablePathChannel(reporting.echarts_js)
  status_accession = publishablePathChannel(statusBuild.accession_status_tsv)
  status_accession_call_counts = publishablePathChannel(statusBuild.accession_call_counts_tsv)
  status_summary = publishablePathChannel(statusBuild.status_summary_json)

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
