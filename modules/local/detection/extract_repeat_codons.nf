process FINALIZE_CALL_CODONS {
    label 'detection'
    tag "${method}:${repeat_residue}"
    publishDir({ "${params.output_dir}/calls/by_method/${method}/${repeat_residue}" }, mode: 'copy', saveAs: { filename ->
        def prefix = "finalized_${method}_${repeat_residue}/"
        filename.startsWith(prefix) ? filename.substring(prefix.length()) : filename
    })

    input:
    tuple val(method), val(repeat_residue), path(call_tsv), path(run_params_tsv)
    path(sequences_tsv)
    path(cds_fasta)

    output:
    tuple val(method), val(repeat_residue), path("finalized_${method}_${repeat_residue}"), emit: finalized_dir

    script:
    def inputCallName = call_tsv.getName()
    def inputCallStem = inputCallName.endsWith('.tsv') ? inputCallName[0..-5] : inputCallName
    def inputWarningName = "${inputCallStem}_codon_warnings.tsv"
    def uniqueCallName = "final_${method}_${repeat_residue}_calls.tsv"
    def uniqueRunParamsName = "final_${method}_${repeat_residue}_run_params.tsv"
    def uniqueWarningName = "final_${method}_${repeat_residue}_codon_warnings.tsv"
    """
    ${params.python_bin} -m homorepeat.cli.extract_repeat_codons \
      --calls-tsv ${call_tsv} \
      --sequences-tsv ${sequences_tsv} \
      --cds-fasta ${cds_fasta} \
      --outdir finalized_${method}_${repeat_residue}

    mv finalized_${method}_${repeat_residue}/${inputCallName} finalized_${method}_${repeat_residue}/${uniqueCallName}
    mv finalized_${method}_${repeat_residue}/${inputWarningName} finalized_${method}_${repeat_residue}/${uniqueWarningName}
    cp ${run_params_tsv} finalized_${method}_${repeat_residue}/${uniqueRunParamsName}
    """
}
