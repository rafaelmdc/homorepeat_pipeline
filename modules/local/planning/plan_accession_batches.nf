process PLAN_ACCESSION_BATCHES {
    label 'planning'
    publishDir("${params.run_root}/internal/planning", mode: 'copy', saveAs: { filename ->
        filename.startsWith('planning_artifacts/') ? filename.substring('planning_artifacts/'.length()) : filename
    })

    input:
    path(accessions_file)

    output:
    path("planning_artifacts/accession_batches.tsv"), emit: batch_table
    path("planning_artifacts/accession_resolution.tsv"), emit: accession_resolution
    path("planning_artifacts/selected_accessions.txt"), emit: selected_accessions
    path("planning_artifacts/batch_manifests"), emit: batch_manifests_dir

    script:
    def apiKeyArg = params.ncbi_api_key ? "--api-key '${params.ncbi_api_key}'" : ""
    """
    ${params.python_bin} -m homorepeat.cli.plan_accession_batches \
      --accessions-file ${accessions_file} \
      --datasets-bin ${params.datasets_bin} \
      ${apiKeyArg} \
      --target-batch-size ${params.batch_size} \
      --outdir planning_artifacts
    """
}
