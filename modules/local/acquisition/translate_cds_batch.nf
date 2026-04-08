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
    for filename in genomes.tsv taxonomy.tsv sequences.tsv download_manifest.tsv download_stage_status.json normalize_stage_status.json; do
      if [ -f "${normalized_batch_dir}/\$filename" ]; then
        cp "${normalized_batch_dir}/\$filename" "\$outdir/\$filename"
      fi
    done

    if [ -f "${normalized_batch_dir}/normalization_warnings.tsv" ]; then
      cp "${normalized_batch_dir}/normalization_warnings.tsv" "\$outdir/normalization_warnings.tsv"
    fi

    if [ -f "${normalized_batch_dir}/cds.fna" ]; then
      ln "${normalized_batch_dir}/cds.fna" "\$outdir/cds.fna" || cp "${normalized_batch_dir}/cds.fna" "\$outdir/cds.fna"
    fi

    ${params.python_bin} -m homorepeat.cli.translate_cds \
      --sequences-tsv "\$outdir/sequences.tsv" \
      --cds-fasta "\$outdir/cds.fna" \
      --batch-id ${batch_id} \
      --stage-status-out "\$outdir/translate_stage_status.json" \
      --outdir "\$outdir"
    """
}
