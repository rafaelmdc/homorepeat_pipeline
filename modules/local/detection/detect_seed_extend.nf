process DETECT_SEED_EXTEND {
    label 'detection'
    tag "${repeat_residue}"

    input:
    val(repeat_residue)
    path(proteins_tsv)
    path(proteins_fasta)

    output:
    tuple val('seed_extend'), val(repeat_residue), path("seed_extend_${repeat_residue}_calls.tsv"), path("seed_extend_${repeat_residue}_run_params.tsv"), emit: calls

    script:
    """
    ${params.python_bin} -m homorepeat.cli.detect_seed_extend \
      --proteins-tsv ${proteins_tsv} \
      --proteins-fasta ${proteins_fasta} \
      --repeat-residue ${repeat_residue} \
      --seed-window-size ${params.seed_extend_seed_window_size} \
      --seed-min-target-count ${params.seed_extend_seed_min_target_count} \
      --extend-window-size ${params.seed_extend_extend_window_size} \
      --extend-min-target-count ${params.seed_extend_extend_min_target_count} \
      --min-total-length ${params.seed_extend_min_total_length} \
      --outdir detect_seed_extend_${repeat_residue}

    cp detect_seed_extend_${repeat_residue}/seed_extend_calls.tsv seed_extend_${repeat_residue}_calls.tsv
    cp detect_seed_extend_${repeat_residue}/run_params.tsv seed_extend_${repeat_residue}_run_params.tsv
    """
}
