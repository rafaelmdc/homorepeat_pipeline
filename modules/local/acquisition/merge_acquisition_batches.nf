process MERGE_ACQUISITION_BATCHES {
    label 'acquisition_merge'

    input:
    path(translated_batch_dirs, stageAs: 'batch??')

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
    def batchInputs = translated_batch_dirs instanceof List ? translated_batch_dirs : [translated_batch_dirs]
    def batchArgs = batchInputs.collect { "--batch-inputs '${it}'" }.join(' ')
    """
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
