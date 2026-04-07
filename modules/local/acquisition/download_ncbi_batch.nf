process DOWNLOAD_NCBI_BATCH {
    label 'acquisition_download'
    tag { batch_manifest.baseName }

    input:
    path(batch_manifest)

    output:
    tuple val(batch_manifest.baseName), path("raw_batch"), emit: raw_batch

    script:
    def batchId = batch_manifest.baseName
    def apiKeyArg = params.ncbi_api_key ? "--api-key '${params.ncbi_api_key}'" : ""
    def cacheDirArg = params.ncbi_cache_dir ? "--cache-dir '${params.ncbi_cache_dir}'" : ""
    def dehydratedArg = params.ncbi_dehydrated ? "--dehydrated" : ""
    def rehydrateArg = params.ncbi_rehydrate ? "--rehydrate" : ""
    def rehydrateWorkersArg = params.ncbi_rehydrate_workers ? "--rehydrate-workers ${params.ncbi_rehydrate_workers}" : ""
    """
    ${params.python_bin} -m homorepeat.cli.download_ncbi_packages \
      --batch-manifest ${batch_manifest} \
      --batch-id ${batchId} \
      --datasets-bin ${params.datasets_bin} \
      ${apiKeyArg} \
      ${cacheDirArg} \
      ${dehydratedArg} \
      ${rehydrateArg} \
      ${rehydrateWorkersArg} \
      --outdir raw_batch
    """
}
