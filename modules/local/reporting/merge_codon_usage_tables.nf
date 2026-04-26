process MERGE_CODON_USAGE_TABLES_TASK {
    label 'reporting'

    input:
    path(codon_usage_tsvs)

    output:
    path('repeat_call_codon_usage.tsv'), emit: repeat_call_codon_usage_tsv

    script:
    def codonUsageInputs = codon_usage_tsvs instanceof List ? codon_usage_tsvs : [codon_usage_tsvs]
    def codonUsageArgs = codonUsageInputs.collect { "--codon-usage-tsv '${it}'" }.join(' ')
    """
    ${params.python_bin} -m homorepeat.cli.merge_codon_usage_tables \
      ${codonUsageArgs} \
      --outdir merged_codon_usage_tmp

    mv merged_codon_usage_tmp/repeat_call_codon_usage.tsv repeat_call_codon_usage.tsv
    """
}

workflow MERGE_CODON_USAGE_TABLES {
    take:
    codon_usage_tsvs

    main:
    collectedCodonUsageTsvs = codon_usage_tsvs.collect()
    merged = MERGE_CODON_USAGE_TABLES_TASK(collectedCodonUsageTsvs)

    emit:
    repeat_call_codon_usage_tsv = merged.repeat_call_codon_usage_tsv
}
