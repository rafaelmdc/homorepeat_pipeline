process DETECT_SEED_EXTEND {
    label 'detection'
    tag "${batch_id}:${repeat_residue}"

    input:
    tuple val(batch_id), val(repeat_residue), path(batch_dir)

    output:
    tuple val(batch_id), val('seed_extend'), val(repeat_residue), path("seed_extend_${repeat_residue}_calls.tsv"), path("seed_extend_${repeat_residue}_run_params.tsv"), emit: calls
    tuple val(batch_id), val('seed_extend'), val(repeat_residue), path("detect_status.json"), emit: stage_status

    script:
    """
    ${params.python_bin} -m homorepeat.cli.detect_seed_extend \
      --proteins-tsv ${batch_dir}/proteins.tsv \
      --proteins-fasta ${batch_dir}/proteins.faa \
      --repeat-residue ${repeat_residue} \
      --batch-id ${batch_id} \
      --fail-soft \
      --status-out detect_seed_extend_${repeat_residue}/detect_status.json \
      --seed-window-size ${params.seed_extend_seed_window_size} \
      --seed-min-target-count ${params.seed_extend_seed_min_target_count} \
      --extend-window-size ${params.seed_extend_extend_window_size} \
      --extend-min-target-count ${params.seed_extend_extend_min_target_count} \
      --min-total-length ${params.seed_extend_min_total_length} \
      --outdir detect_seed_extend_${repeat_residue}

    cp detect_seed_extend_${repeat_residue}/seed_extend_calls.tsv seed_extend_${repeat_residue}_calls.tsv
    cp detect_seed_extend_${repeat_residue}/run_params.tsv seed_extend_${repeat_residue}_run_params.tsv
    cp detect_seed_extend_${repeat_residue}/detect_status.json detect_status.json
    """
}
