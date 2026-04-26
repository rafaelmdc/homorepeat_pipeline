nextflow.enable.dsl = 2

include { PLAN_ACCESSION_BATCHES } from '../modules/local/planning/plan_accession_batches'
include { DOWNLOAD_NCBI_BATCH } from '../modules/local/acquisition/download_ncbi_batch'
include { NORMALIZE_CDS_BATCH } from '../modules/local/acquisition/normalize_cds_batch'
include { TRANSLATE_CDS_BATCH } from '../modules/local/acquisition/translate_cds_batch'
include { MERGE_ACQUISITION_BATCHES } from '../modules/local/acquisition/merge_acquisition_batches'

workflow ACQUISITION_FROM_ACCESSIONS {
    if( !params.accessions_file ) {
        error "params.accessions_file is required"
    }
    if( !params.taxonomy_db ) {
        error "params.taxonomy_db is required"
    }
    def acquisitionPublishMode = (params.acquisition_publish_mode ?: 'raw').toString().trim().toLowerCase()
    if( !['raw', 'merged'].contains(acquisitionPublishMode) ) {
        error "params.acquisition_publish_mode must be one of: raw, merged"
    }

    def accessionsFile = file(params.accessions_file, checkIfExists: true)
    def taxonomyDb = file(params.taxonomy_db, checkIfExists: true)

    planning = PLAN_ACCESSION_BATCHES(Channel.value(accessionsFile))
    batchManifestCh = planning.batch_manifests_dir.flatMap { manifestsDir ->
        def manifestRoot = manifestsDir.toFile()
        def manifestFiles = manifestRoot.listFiles()?.findAll { it.name.endsWith('.tsv') }?.sort { it.name } ?: []
        manifestFiles.collect { file(it) }
    }
    downloaded = DOWNLOAD_NCBI_BATCH(batchManifestCh)
    normalized = NORMALIZE_CDS_BATCH(downloaded.raw_batch, Channel.value(taxonomyDb))
    translated = TRANSLATE_CDS_BATCH(normalized.normalized_batch)
    batchRows = normalized.normalized_batch.join(translated.translated_batch)
    batchInputs = batchRows.toList().map { rows ->
        tuple(
            rows.collect { row -> row[0] },
            rows.collect { row -> row[1] },
            rows.collect { row -> row[2] },
        )
    }
    def mergedGenomesTsvCh = Channel.empty()
    def mergedTaxonomyTsvCh = Channel.empty()
    def mergedSequencesTsvCh = Channel.empty()
    def mergedProteinsTsvCh = Channel.empty()
    def mergedCdsFastaCh = Channel.empty()
    def mergedProteinsFastaCh = Channel.empty()
    def mergedDownloadManifestTsvCh = Channel.empty()
    def mergedNormalizationWarningsTsvCh = Channel.empty()
    def mergedAcquisitionValidationCh = Channel.empty()

    if( acquisitionPublishMode == 'merged' ) {
        merged = MERGE_ACQUISITION_BATCHES(batchInputs)
        mergedGenomesTsvCh = merged.genomes_tsv
        mergedTaxonomyTsvCh = merged.taxonomy_tsv
        mergedSequencesTsvCh = merged.sequences_tsv
        mergedProteinsTsvCh = merged.proteins_tsv
        mergedCdsFastaCh = merged.cds_fasta
        mergedProteinsFastaCh = merged.proteins_fasta
        mergedDownloadManifestTsvCh = merged.download_manifest_tsv
        mergedNormalizationWarningsTsvCh = merged.normalization_warnings_tsv
        mergedAcquisitionValidationCh = merged.acquisition_validation
    }

    emit:
    batch_table = planning.batch_table
    accession_resolution = planning.accession_resolution
    batch_rows = batchRows
    batch_inputs = batchInputs
    genomes_tsv = mergedGenomesTsvCh
    taxonomy_tsv = mergedTaxonomyTsvCh
    sequences_tsv = mergedSequencesTsvCh
    proteins_tsv = mergedProteinsTsvCh
    cds_fasta = mergedCdsFastaCh
    proteins_fasta = mergedProteinsFastaCh
    download_manifest_tsv = mergedDownloadManifestTsvCh
    normalization_warnings_tsv = mergedNormalizationWarningsTsvCh
    acquisition_validation = mergedAcquisitionValidationCh
}
