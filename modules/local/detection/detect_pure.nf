process DETECT_PURE {
    label 'detection'
    tag "${batch_id}:${repeat_residue}"

    input:
    tuple val(batch_id), val(repeat_residue), path(batch_dir)

    output:
    tuple val(batch_id), val('pure'), val(repeat_residue), path("pure_${repeat_residue}_calls.tsv"), path("pure_${repeat_residue}_run_params.tsv"), emit: calls
    tuple val(batch_id), val('pure'), val(repeat_residue), path("detect_status.json"), emit: stage_status

    script:
    """
    ${params.python_bin} -m homorepeat.cli.detect_pure \
      --proteins-tsv ${batch_dir}/proteins.tsv \
      --proteins-fasta ${batch_dir}/proteins.faa \
      --repeat-residue ${repeat_residue} \
      --batch-id ${batch_id} \
      --fail-soft \
      --status-out detect_pure_${repeat_residue}/detect_status.json \
      --min-repeat-count ${params.pure_min_repeat_count} \
      --outdir detect_pure_${repeat_residue}

    cp detect_pure_${repeat_residue}/pure_calls.tsv pure_${repeat_residue}_calls.tsv
    cp detect_pure_${repeat_residue}/run_params.tsv pure_${repeat_residue}_run_params.tsv
    cp detect_pure_${repeat_residue}/detect_status.json detect_status.json
    """
}
