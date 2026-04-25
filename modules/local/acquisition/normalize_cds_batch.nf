process NORMALIZE_CDS_BATCH {
    label 'acquisition_normalize'
    tag { batch_id }
    publishDir(
        "${params.run_root}/publish/acquisition/batches/${batch_id}",
        mode: 'copy',
        enabled: false,
        saveAs: { filename ->
        def sourceName = filename.toString()
        if( !sourceName.startsWith('publish_batch/') ) {
            return null
        }
        def publishedName = sourceName.substring('publish_batch/'.length())
        ['taxonomy.tsv', 'sequences.tsv', 'cds.fna'].contains(publishedName) ? publishedName : null
    })

    input:
    tuple val(batch_id), path(raw_batch_dir)
    path(taxonomy_db)

    output:
    tuple val(batch_id), path("normalized_batch"), emit: normalized_batch
    path("publish_batch/taxonomy.tsv")
    path("publish_batch/sequences.tsv")
    path("publish_batch/cds.fna")

    script:
    """
    ${params.python_bin} -m homorepeat.cli.normalize_cds \
      --package-dir ${raw_batch_dir}/ncbi_package \
      --taxonomy-db ${taxonomy_db} \
      --taxon-weaver-bin ${params.taxon_weaver_bin} \
      --batch-id ${batch_id} \
      --stage-status-out normalized_batch/normalize_stage_status.json \
      --outdir normalized_batch

    cp ${raw_batch_dir}/download_stage_status.json normalized_batch/download_stage_status.json

    mkdir -p publish_batch
    ln -s ../normalized_batch/taxonomy.tsv publish_batch/taxonomy.tsv
    ln -s ../normalized_batch/sequences.tsv publish_batch/sequences.tsv
    ln -s ../normalized_batch/cds.fna publish_batch/cds.fna
    """
}
