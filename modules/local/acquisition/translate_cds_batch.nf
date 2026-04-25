process TRANSLATE_CDS_BATCH {
    label 'acquisition_translate'
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
        [
            'genomes.tsv',
            'proteins.tsv',
            'proteins.faa',
            'download_manifest.tsv',
            'normalization_warnings.tsv',
            'acquisition_validation.json',
        ].contains(publishedName) ? publishedName : null
    })

    input:
    tuple val(batch_id), path(normalized_batch_dir)

    output:
    tuple val(batch_id), path("translated_batch"), emit: translated_batch
    path("publish_batch/genomes.tsv")
    path("publish_batch/proteins.tsv")
    path("publish_batch/proteins.faa")
    path("publish_batch/download_manifest.tsv")
    path("publish_batch/normalization_warnings.tsv")
    path("publish_batch/acquisition_validation.json")

    script:
    """
    outdir=translated_batch

    mkdir -p "\$outdir"
    for filename in genomes.tsv download_manifest.tsv; do
      if [ -f "${normalized_batch_dir}/\$filename" ]; then
        cp "${normalized_batch_dir}/\$filename" "\$outdir/\$filename"
      fi
    done

    if [ -f "${normalized_batch_dir}/normalization_warnings.tsv" ]; then
      cp "${normalized_batch_dir}/normalization_warnings.tsv" "\$outdir/normalization_warnings.tsv"
    fi

    ${params.python_bin} -m homorepeat.cli.translate_cds \
      --sequences-tsv "${normalized_batch_dir}/sequences.tsv" \
      --cds-fasta "${normalized_batch_dir}/cds.fna" \
      --batch-id ${batch_id} \
      --stage-status-out "\$outdir/translate_stage_status.json" \
      --outdir "\$outdir"

    mkdir -p publish_batch
    ln -s ../translated_batch/genomes.tsv publish_batch/genomes.tsv
    ln -s ../translated_batch/proteins.tsv publish_batch/proteins.tsv
    ln -s ../translated_batch/proteins.faa publish_batch/proteins.faa
    ln -s ../translated_batch/download_manifest.tsv publish_batch/download_manifest.tsv
    ln -s ../translated_batch/normalization_warnings.tsv publish_batch/normalization_warnings.tsv
    ln -s ../translated_batch/acquisition_validation.json publish_batch/acquisition_validation.json
    """
}
