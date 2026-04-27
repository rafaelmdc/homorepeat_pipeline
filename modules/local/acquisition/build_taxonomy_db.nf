process BUILD_TAXONOMY_DB {
    label 'taxonomy_build'
    tag 'ncbi_taxonomy'

    publishDir params.taxonomy_cache_dir, mode: 'copy', overwrite: true

    output:
    path("ncbi_taxonomy.sqlite"), emit: taxonomy_db
    path("taxdump.tar.gz"), emit: taxdump
    path("ncbi_taxonomy_build.json"), emit: build_report

    script:
    """
    ${params.taxon_weaver_bin} build-db \
      --download \
      --dump taxdump.tar.gz \
      --db ncbi_taxonomy.sqlite \
      --report-json ncbi_taxonomy_build.json
    """
}
