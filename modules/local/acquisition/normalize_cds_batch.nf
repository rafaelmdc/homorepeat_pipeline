process NORMALIZE_CDS_BATCH {
    label 'acquisition_normalize'
    tag { batch_id }

    input:
    tuple val(batch_id), path(raw_batch_dir)
    path(taxonomy_db)

    output:
    tuple val(batch_id), path("normalized_batch"), emit: normalized_batch

    script:
    """
    ${params.python_bin} -m homorepeat.cli.normalize_cds \
      --package-dir ${raw_batch_dir}/ncbi_package \
      --taxonomy-db ${taxonomy_db} \
      --taxon-weaver-bin ${params.taxon_weaver_bin} \
      --batch-id ${batch_id} \
      --outdir normalized_batch
    """
}
