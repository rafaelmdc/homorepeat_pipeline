nextflow.enable.dsl = 2

include { DETECT_PURE } from '../modules/local/detection/detect_pure'
include { DETECT_SEED_EXTEND } from '../modules/local/detection/detect_seed_extend'
include { DETECT_THRESHOLD } from '../modules/local/detection/detect_threshold'
include {
    FINALIZE_CALL_CODONS as FINALIZE_PURE_CALL_CODONS
    FINALIZE_CALL_CODONS as FINALIZE_SEED_EXTEND_CALL_CODONS
    FINALIZE_CALL_CODONS as FINALIZE_THRESHOLD_CALL_CODONS
} from '../modules/local/detection/extract_repeat_codons'

workflow DETECTION_FROM_ACQUISITION {
    take:
    translated_batch_rows

    main:
    if( !params.run_pure && !params.run_threshold && !params.run_seed_extend ) {
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
    def detectStatusCh = Channel.empty()
    def finalizeStatusCh = Channel.empty()
    def batchDirLookup = {
        translated_batch_rows.flatMap { rows ->
            rows.collect { row -> tuple(row[0], row[1]) }
        }
    }

    if( params.run_pure ) {
        pureDetection = DETECT_PURE(
            translated_batch_rows.flatMap { rows ->
                rows.collectMany { row ->
                    repeatResidues.collect { residue -> tuple(row[0], residue, row[1]) }
                }
            }
        )
        pureFinalize = FINALIZE_PURE_CALL_CODONS(
            pureDetection.calls.join(batchDirLookup())
        )
        finalizedCallCh = finalizedCallCh.mix(pureFinalize.finalized_dir)
        detectStatusCh = detectStatusCh.mix(pureDetection.stage_status)
        finalizeStatusCh = finalizeStatusCh.mix(pureFinalize.stage_status)
    }

    if( params.run_threshold ) {
        thresholdDetection = DETECT_THRESHOLD(
            translated_batch_rows.flatMap { rows ->
                rows.collectMany { row ->
                    repeatResidues.collect { residue -> tuple(row[0], residue, row[1]) }
                }
            }
        )
        thresholdFinalize = FINALIZE_THRESHOLD_CALL_CODONS(
            thresholdDetection.calls.join(batchDirLookup())
        )
        finalizedCallCh = finalizedCallCh.mix(thresholdFinalize.finalized_dir)
        detectStatusCh = detectStatusCh.mix(thresholdDetection.stage_status)
        finalizeStatusCh = finalizeStatusCh.mix(thresholdFinalize.stage_status)
    }

    if( params.run_seed_extend ) {
        seedExtendDetection = DETECT_SEED_EXTEND(
            translated_batch_rows.flatMap { rows ->
                rows.collectMany { row ->
                    repeatResidues.collect { residue -> tuple(row[0], residue, row[1]) }
                }
            }
        )
        seedExtendFinalize = FINALIZE_SEED_EXTEND_CALL_CODONS(
            seedExtendDetection.calls.join(batchDirLookup())
        )
        finalizedCallCh = finalizedCallCh.mix(seedExtendFinalize.finalized_dir)
        detectStatusCh = detectStatusCh.mix(seedExtendDetection.stage_status)
        finalizeStatusCh = finalizeStatusCh.mix(seedExtendFinalize.stage_status)
    }

    finalizedCallRows = finalizedCallCh.toList()
    detectStatusRows = detectStatusCh.toList()
    finalizeStatusRows = finalizeStatusCh.toList()

    emit:
    call_tsvs = finalizedCallRows.map { rows ->
        rows.collect { row ->
            def batch_id = row[0]
            def method = row[1]
            def repeatResidue = row[2]
            def finalizedDir = row[3]
            finalizedDir.resolve("final_${method}_${repeatResidue}_${batch_id}_calls.tsv")
        }
    }
    run_params_tsvs = finalizedCallRows.map { rows ->
        rows.collect { row ->
            def batch_id = row[0]
            def method = row[1]
            def repeatResidue = row[2]
            def finalizedDir = row[3]
            finalizedDir.resolve("final_${method}_${repeatResidue}_${batch_id}_run_params.tsv")
        }
    }
    detect_status_jsons = detectStatusRows.map { rows ->
        rows.collect { row -> row[3] }
    }
    finalize_status_jsons = finalizeStatusRows.map { rows ->
        rows.collect { row -> row[3] }
    }
}
