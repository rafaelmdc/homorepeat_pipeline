process DETECT_THRESHOLD {
    label 'detection'
    tag "${repeat_residue}"

    input:
    val(repeat_residue)
    path(proteins_tsv)
    path(proteins_fasta)

    output:
    tuple val('threshold'), val(repeat_residue), path("threshold_${repeat_residue}_calls.tsv"), path("threshold_${repeat_residue}_run_params.tsv"), emit: calls

    script:
    """
    ${params.python_bin} -m homorepeat.cli.detect_threshold \
      --proteins-tsv ${proteins_tsv} \
      --proteins-fasta ${proteins_fasta} \
      --repeat-residue ${repeat_residue} \
      --outdir detect_threshold_${repeat_residue}

    cp detect_threshold_${repeat_residue}/threshold_calls.tsv threshold_${repeat_residue}_calls.tsv
    cp detect_threshold_${repeat_residue}/run_params.tsv threshold_${repeat_residue}_run_params.tsv
    """
}
