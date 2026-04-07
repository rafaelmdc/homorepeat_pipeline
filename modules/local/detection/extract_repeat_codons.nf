process FINALIZE_CALL_CODONS {
    label 'detection'
    tag "${batch_id}:${method}:${repeat_residue}"
    publishDir({ "${params.output_dir}/detection/finalized/${method}/${repeat_residue}" }, mode: 'copy', saveAs: { filename ->
        def prefix = "finalized_${method}_${repeat_residue}_${batch_id}/"
        filename.startsWith(prefix) ? filename.substring(prefix.length()) : filename
    })

    input:
    tuple val(batch_id), val(method), val(repeat_residue), path(call_tsv), path(run_params_tsv), path(batch_dir)

    output:
    tuple val(batch_id), val(method), val(repeat_residue), path("finalized_${method}_${repeat_residue}_${batch_id}"), emit: finalized_dir
    tuple val(batch_id), val(method), val(repeat_residue), path("finalize_status.json"), emit: stage_status

    script:
    def inputCallName = call_tsv.getName()
    def inputCallStem = inputCallName.endsWith('.tsv') ? inputCallName[0..-5] : inputCallName
    def inputWarningName = "${inputCallStem}_codon_warnings.tsv"
    def inputCodonUsageName = "${inputCallStem}_codon_usage.tsv"
    def uniqueCallName = "final_${method}_${repeat_residue}_${batch_id}_calls.tsv"
    def uniqueRunParamsName = "final_${method}_${repeat_residue}_${batch_id}_run_params.tsv"
    def uniqueWarningName = "final_${method}_${repeat_residue}_${batch_id}_codon_warnings.tsv"
    def uniqueCodonUsageName = "final_${method}_${repeat_residue}_${batch_id}_codon_usage.tsv"
    """
    ${params.python_bin} -m homorepeat.cli.extract_repeat_codons \
      --calls-tsv ${call_tsv} \
      --sequences-tsv ${batch_dir}/sequences.tsv \
      --cds-fasta ${batch_dir}/cds.fna \
      --batch-id ${batch_id} \
      --method ${method} \
      --repeat-residue ${repeat_residue} \
      --fail-soft \
      --status-out finalized_${method}_${repeat_residue}_${batch_id}/finalize_status.json \
      --outdir finalized_${method}_${repeat_residue}_${batch_id}

    mv finalized_${method}_${repeat_residue}_${batch_id}/${inputCallName} finalized_${method}_${repeat_residue}_${batch_id}/${uniqueCallName}
    mv finalized_${method}_${repeat_residue}_${batch_id}/${inputWarningName} finalized_${method}_${repeat_residue}_${batch_id}/${uniqueWarningName}
    mv finalized_${method}_${repeat_residue}_${batch_id}/${inputCodonUsageName} finalized_${method}_${repeat_residue}_${batch_id}/${uniqueCodonUsageName}
    cp ${run_params_tsv} finalized_${method}_${repeat_residue}_${batch_id}/${uniqueRunParamsName}
    cp finalized_${method}_${repeat_residue}_${batch_id}/finalize_status.json finalize_status.json
    """
}
