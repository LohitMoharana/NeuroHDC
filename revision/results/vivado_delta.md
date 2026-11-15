# Vivado 2022.2, xc7z010clg225-3, OOC synth + default impl, clock constraint 1000 ns (1 MHz), vectorless power
| metric | baseline top_shde_wrapper (re-run) | submitted | top_shde_classifier | delta |
|---|---|---|---|---|
| Slice LUTs | 5321 | 5321 | 7268 | +1947 |
| LUT as logic / as memory | 4297 / 1024 | same | 6244 / 1024 | +1947 / 0 |
| Slice registers | 8760 | 8760 | 9130 | +370 |
| Block RAM tiles | 42 | 42 | 42 | 0 (prototype ROM mapped to LUTs: assoc_mem rom 256x128 -> LUT) |
| DSPs | 0 | 0 | 0 | 0 |
| WNS (ns) | 986.810 | 986.810 | 987.156 | at 1 MHz, uninformative |
| Dynamic power (W, tool, 3 decimals) | 0.001 | 0.001 | 0.001 | not resolvable |
Reports: revision/vivado/out_baseline/, revision/vivado/out_classifier_final/ (run in D:\nhdc_vv\cls; long worktree path broke Vivado).
First classifier attempt used an unaligned query[qoff -: CHUNK] part-select -> 21,498 LUT (device overflow); fixed with an aligned fold-indexed mux, simulation re-verified.

## BRAM attempt (ram_style="block" on the assoc_mem prototype array)
Result identical to the LUT version: 7268 LUT / 9130 FF / 42 BRAM / 0 DSP, WNS 987.156 (reports in revision/vivado/out_classifier_bram/).
Synthesis log still reports "assoc_mem | rom | 256x128 | LUT": Vivado ignores the block hint for this constant-initialised, never-written array.
Env note: Vivado launched from the Bash tool intermittently failed with spurious "couldn't read file" errors; launching from PowerShell Start-Process worked.
