# Vivado re-run for the added classifier (revision prep; not executed here)

Vivado is not installed on the authoring laptop, so **no synthesis/utilization/power numbers exist yet** for
the classifier. Everything below is ready to run on the machine that produced the submitted results.

1. Baseline sanity (must reproduce 5321 LUT / 8760 FF / 42 BRAM / 0 DSP, 1.0 mW):
   `vivado -mode batch -source revision/vivado/run_classifier.tcl -tclargs top_shde_wrapper 1000 revision/vivado/out_baseline`
2. Classifier:
   `vivado -mode batch -source revision/vivado/run_classifier.tcl -tclargs top_shde_classifier 1000 revision/vivado/out_classifier`
3. Report the delta (LUT, FF, BRAM, DSP, WNS, power) from `*_utilization_placed.rpt`, `*_timing_summary_routed.rpt`, `*_power_routed.rpt`.

Things to check on that machine: (a) `proto_chunks.dat` is found by `$readmemb` (otherwise the ROM synthesises as zeros -
look for a Synth 8-xxxx readmem warning and an unexpectedly tiny BRAM delta); (b) DSP stays 0; (c) the BRAM delta
(the 5x4096-bit prototype ROM is 160 x 128-bit words, width-driven BRAM use).

Caveat for the paper: the committed `constraints.xdc` says "100 MHz" in its comment but declares
`create_clock -period 1000.000` (1 MHz). The submitted timing slack (WNS 986.8 ns) and the 1.0 mW vectorless dynamic
power are at 1 MHz. Both runs above keep 1000 ns so they stay comparable; a 100 MHz (10 ns) run is a separate,
clearly-labelled extra if wanted.
