process TRANSLATE_CDS_BATCH {
    label 'acquisition_normalize'
    tag { batch_id }

    input:
    tuple val(batch_id), path(normalized_batch_dir)

    output:
    tuple val(batch_id), path("translated_batch"), emit: translated_batch

    script:
    """
    outdir=translated_batch

    mkdir -p "\$outdir"
    cp -R ${normalized_batch_dir}/. "\$outdir"/

    ${params.python_bin} -m homorepeat.cli.translate_cds \
      --sequences-tsv "\$outdir/sequences.tsv" \
      --cds-fasta "\$outdir/cds.fna" \
      --batch-id ${batch_id} \
      --outdir "\$outdir"
    """
}
