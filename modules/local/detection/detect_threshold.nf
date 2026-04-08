process DETECT_THRESHOLD {
    label 'detection'
    tag "${batch_id}:${repeat_residue}"

    input:
    tuple val(batch_id), val(repeat_residue), path(batch_dir)

    output:
    tuple val(batch_id), val('threshold'), val(repeat_residue), path("threshold_${repeat_residue}_calls.tsv"), path("threshold_${repeat_residue}_run_params.tsv"), emit: calls
    tuple val(batch_id), val('threshold'), val(repeat_residue), path("detect_status.json"), emit: stage_status

    script:
    """
    ${params.python_bin} -m homorepeat.cli.detect_threshold \
      --proteins-tsv ${batch_dir}/proteins.tsv \
      --proteins-fasta ${batch_dir}/proteins.faa \
      --repeat-residue ${repeat_residue} \
      --batch-id ${batch_id} \
      --status-out detect_threshold_${repeat_residue}/detect_status.json \
      --window-size ${params.threshold_window_size} \
      --min-target-count ${params.threshold_min_target_count} \
      --outdir detect_threshold_${repeat_residue}

    cp detect_threshold_${repeat_residue}/threshold_calls.tsv threshold_${repeat_residue}_calls.tsv
    cp detect_threshold_${repeat_residue}/run_params.tsv threshold_${repeat_residue}_run_params.tsv
    cp detect_threshold_${repeat_residue}/detect_status.json detect_status.json
    """
}
