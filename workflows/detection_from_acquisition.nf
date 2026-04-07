nextflow.enable.dsl = 2

include { DETECT_PURE } from '../modules/local/detection/detect_pure'
include { DETECT_THRESHOLD } from '../modules/local/detection/detect_threshold'
include {
    FINALIZE_CALL_CODONS as FINALIZE_PURE_CALL_CODONS
    FINALIZE_CALL_CODONS as FINALIZE_THRESHOLD_CALL_CODONS
} from '../modules/local/detection/extract_repeat_codons'

workflow DETECTION_FROM_ACQUISITION {
    take:
    sequences_tsv
    cds_fasta
    proteins_tsv
    proteins_fasta

    main:
    if( !params.run_pure && !params.run_threshold ) {
        error "At least one detection path must be enabled"
    }

    def repeatResidues = params.repeat_residues
        .toString()
        .split(',')
        .collect { it.trim().toUpperCase() }
        .findAll { it }
        .unique()

    if( repeatResidues.isEmpty() ) {
        error "params.repeat_residues must contain at least one residue symbol"
    }

    def finalizedCallCh = Channel.empty()

    if( params.run_pure ) {
        repeatResidues.each { residue ->
            pureDetection = DETECT_PURE(residue, proteins_tsv, proteins_fasta)
            pureFinalize = FINALIZE_PURE_CALL_CODONS(pureDetection.calls, sequences_tsv, cds_fasta)
            finalizedCallCh = finalizedCallCh.mix(pureFinalize.finalized_dir)
        }
    }

    if( params.run_threshold ) {
        repeatResidues.each { residue ->
            thresholdDetection = DETECT_THRESHOLD(residue, proteins_tsv, proteins_fasta)
            thresholdFinalize = FINALIZE_THRESHOLD_CALL_CODONS(
                thresholdDetection.calls,
                sequences_tsv,
                cds_fasta,
            )
            finalizedCallCh = finalizedCallCh.mix(thresholdFinalize.finalized_dir)
        }
    }

    emit:
    call_tsv = finalizedCallCh.map { method, repeatResidue, finalizedDir -> finalizedDir.resolve("final_${method}_${repeatResidue}_calls.tsv") }
    run_params_tsv = finalizedCallCh.map { method, repeatResidue, finalizedDir -> finalizedDir.resolve("final_${method}_${repeatResidue}_run_params.tsv") }
}
