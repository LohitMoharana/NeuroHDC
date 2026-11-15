# -----------------------------------------------------------------------------
# NeuroHDC revision-prep: Vivado batch flow for the added Hamming associative memory.
# NOT RUN on the authoring laptop (Vivado is not installed there) -- run on the machine
# that produced the submitted 5,321-LUT result (Vivado 2022.2).
#
#   vivado -mode batch -source revision/vivado/run_classifier.tcl -tclargs <top> <clk_period_ns> <outdir>
#   e.g. vivado -mode batch -source revision/vivado/run_classifier.tcl -tclargs top_shde_wrapper    1000 revision/vivado/out_baseline
#        vivado -mode batch -source revision/vivado/run_classifier.tcl -tclargs top_shde_classifier 1000 revision/vivado/out_classifier
#
# Mirrors the submitted project runs (synth_1_copy_1 / impl_2): part xc7z010clg225-3,
# synth_design -mode out_of_context, default opt/place/phys_opt/route, vectorless report_power,
# clock constraint create_clock -period 1000 (the committed constraints.xdc). Run the unchanged
# top_shde_wrapper FIRST on the same machine to confirm 5321 LUT / 8760 FF / 42 BRAM / 0 DSP is
# reproduced; only then trust the classifier delta.
# -----------------------------------------------------------------------------
set top    [lindex $argv 0]
set period [lindex $argv 1]
set outdir [file normalize [lindex $argv 2]]
set root   [file normalize [file join [file dirname [info script]] .. ..]]
file mkdir $outdir
cd $outdir                                ;# $readmemb("proto_chunks.dat") resolves against the cwd
file copy -force [file join $root revision vivado proto_chunks.dat] $outdir

set part xc7z010clg225-3
read_verilog [file join $root hw rtl delta_tokenizer.v]
read_verilog [file join $root hw rtl hdc_bind_bundle.v]
read_verilog [file join $root hw rtl top_shde_core.v]
if {$top eq "top_shde_wrapper"} {
    read_verilog [file join $root hw rtl top_shde_wrapper.v]
} elseif {$top eq "top_shde_classifier"} {
    read_verilog [file join $root revision rtl assoc_mem.v]
    read_verilog [file join $root revision rtl top_shde_classifier.v]
} else { error "unknown top $top" }

# NOTE: top_shde_core.v $readmemb()s ch0/ch1/ch2/item_up/item_dn/pos .dat from the hard-coded
# absolute path D:/Projects/Personal/NeuroHDC/hw/tb/ (non-ASIC branch). That path must exist on
# this machine (it did for the submitted run); the file is intentionally left unmodified.

set xdc [file join $outdir clk.xdc]
set fh [open $xdc w]
puts $fh "create_clock -period $period -name clk -waveform {0.000 [expr {$period/2.0}]} \[get_ports clk\]"
close $fh

synth_design -top $top -part $part -mode out_of_context
read_xdc -mode out_of_context $xdc
write_checkpoint -force ${top}_synth.dcp
report_utilization -file ${top}_utilization_synth.rpt

opt_design
place_design
phys_opt_design
route_design
write_checkpoint -force ${top}_routed.dcp

report_utilization       -file ${top}_utilization_placed.rpt
report_timing_summary    -file ${top}_timing_summary_routed.rpt
report_power             -file ${top}_power_routed.rpt
report_drc               -file ${top}_drc_routed.rpt
report_route_status      -file ${top}_route_status.rpt
puts "DONE $top period=$period outdir=$outdir"
