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
    """
}
