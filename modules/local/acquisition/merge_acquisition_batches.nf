process MERGE_ACQUISITION_BATCHES {
    label 'acquisition_merge'

    input:
    tuple val(batch_ids), path(normalized_batch_dirs, stageAs: 'normalized_batch??'), path(translated_batch_dirs, stageAs: 'translated_batch??')

    output:
    path("genomes.tsv"), emit: genomes_tsv
    path("taxonomy.tsv"), emit: taxonomy_tsv
    path("sequences.tsv"), emit: sequences_tsv
    path("proteins.tsv"), emit: proteins_tsv
    path("cds.fna"), emit: cds_fasta
    path("proteins.faa"), emit: proteins_fasta
    path("download_manifest.tsv"), emit: download_manifest_tsv
    path("normalization_warnings.tsv"), emit: normalization_warnings_tsv
    path("acquisition_validation.json"), emit: acquisition_validation

    script:
    def batchIdInputs = batch_ids instanceof List ? batch_ids : [batch_ids]
    def normalizedInputs = normalized_batch_dirs instanceof List ? normalized_batch_dirs : [normalized_batch_dirs]
    def translatedInputs = translated_batch_dirs instanceof List ? translated_batch_dirs : [translated_batch_dirs]
    assert batchIdInputs.size() == normalizedInputs.size()
    assert batchIdInputs.size() == translatedInputs.size()
    def assembleBatchViews = batchIdInputs.indices.collect { idx ->
        def batchId = batchIdInputs[idx]
        def normalizedDir = normalizedInputs[idx]
        def translatedDir = translatedInputs[idx]
        """
        mkdir -p "batch_views/${batchId}"
        ln '${normalizedDir}/genomes.tsv' "batch_views/${batchId}/genomes.tsv" || cp '${normalizedDir}/genomes.tsv' "batch_views/${batchId}/genomes.tsv"
        ln '${normalizedDir}/taxonomy.tsv' "batch_views/${batchId}/taxonomy.tsv" || cp '${normalizedDir}/taxonomy.tsv' "batch_views/${batchId}/taxonomy.tsv"
        ln '${normalizedDir}/sequences.tsv' "batch_views/${batchId}/sequences.tsv" || cp '${normalizedDir}/sequences.tsv' "batch_views/${batchId}/sequences.tsv"
        ln '${normalizedDir}/download_manifest.tsv' "batch_views/${batchId}/download_manifest.tsv" || cp '${normalizedDir}/download_manifest.tsv' "batch_views/${batchId}/download_manifest.tsv"
        ln '${normalizedDir}/normalization_warnings.tsv' "batch_views/${batchId}/normalization_warnings.tsv" || cp '${normalizedDir}/normalization_warnings.tsv' "batch_views/${batchId}/normalization_warnings.tsv"
        ln '${normalizedDir}/cds.fna' "batch_views/${batchId}/cds.fna" || cp '${normalizedDir}/cds.fna' "batch_views/${batchId}/cds.fna"
        ln '${translatedDir}/proteins.tsv' "batch_views/${batchId}/proteins.tsv" || cp '${translatedDir}/proteins.tsv' "batch_views/${batchId}/proteins.tsv"
        ln '${translatedDir}/proteins.faa' "batch_views/${batchId}/proteins.faa" || cp '${translatedDir}/proteins.faa' "batch_views/${batchId}/proteins.faa"
        """
    }.join('\n')
    def batchArgs = batchIdInputs.collect { "--batch-inputs 'batch_views/${it}'" }.join(' ')
    """
    mkdir -p batch_views
    ${assembleBatchViews}

    ${params.python_bin} -m homorepeat.cli.merge_acquisition_batches \
      ${batchArgs} \
      --outdir acquisition_artifacts

    mv acquisition_artifacts/genomes.tsv genomes.tsv
    mv acquisition_artifacts/taxonomy.tsv taxonomy.tsv
    mv acquisition_artifacts/sequences.tsv sequences.tsv
    mv acquisition_artifacts/proteins.tsv proteins.tsv
    mv acquisition_artifacts/cds.fna cds.fna
    mv acquisition_artifacts/proteins.faa proteins.faa
    mv acquisition_artifacts/download_manifest.tsv download_manifest.tsv
    mv acquisition_artifacts/normalization_warnings.tsv normalization_warnings.tsv
    mv acquisition_artifacts/acquisition_validation.json acquisition_validation.json
    """
}
