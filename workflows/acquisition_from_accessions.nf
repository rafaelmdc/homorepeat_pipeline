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
    translatedBatchRows = translated.translated_batch.toList()
    translatedBatchDirs = translatedBatchRows.map { rows ->
        rows.collect { row -> row[1] }
    }
    merged = MERGE_ACQUISITION_BATCHES(translatedBatchDirs)

    emit:
    batch_table = planning.batch_table
    batch_rows = translatedBatchRows
    genomes_tsv = merged.genomes_tsv
    taxonomy_tsv = merged.taxonomy_tsv
    sequences_tsv = merged.sequences_tsv
    proteins_tsv = merged.proteins_tsv
    cds_fasta = merged.cds_fasta
    proteins_fasta = merged.proteins_fasta
    download_manifest_tsv = merged.download_manifest_tsv
    normalization_warnings_tsv = merged.normalization_warnings_tsv
    acquisition_validation = merged.acquisition_validation
}
