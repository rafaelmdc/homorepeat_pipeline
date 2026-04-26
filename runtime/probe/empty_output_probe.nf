// Probe: does NF 25.10 accept Channel.empty() in a publish: binding?
//
// Scenarios tested:
//   always_present  — a real file; must always publish correctly.
//   always_empty    — Channel.empty() with no conditional; must not crash.
//   conditional_out — a real file when params.emit_real=true, Channel.empty() when false.
//
// Run both modes:
//   nextflow run empty_output_probe.nf -c probe.config --emit_real true  --outdir out_real
//   nextflow run empty_output_probe.nf -c probe.config --emit_real false --outdir out_empty

process WRITE_FILE {
    output:
    path "out.txt", emit: result

    script:
    """
    echo "probe result" > out.txt
    """
}

workflow {
    main:
    produced       = WRITE_FILE()
    def alwaysEmpty   = Channel.empty()
    def conditionalCh = params.emit_real ? produced.result : Channel.empty()

    publish:
    always_present  = produced.result
    always_empty    = alwaysEmpty
    conditional_out = conditionalCh
}

output {
    always_present  { path 'present' }
    always_empty    { path 'empty'   }
    conditional_out { path 'cond'    }
}
