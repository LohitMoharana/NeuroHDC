# Vivado scaling: D = 1024, 2048 (this session) against the submitted D = 4096

Part xc7z010clg225-3, Vivado 2022.2, out-of-context synthesis, default place/route, vectorless power, same flow as
`vivado/run_classifier.tcl` (re-used as `vivado/run_dim.tcl`). Core, tokenizer and binder RTL are the submitted files (the
core is already parameterised in D/CHUNK/FOLDS; only the wrapper/classifier tops were regenerated for the new D by
`gen_dim_rtl.py`; WINDOW_SIZE=256 and CHUNK=128 unchanged). Reports: `vivado/out_dim/<run>/`; raw table: `results/vivado_dim.json`.
"Classifier" uses the revision `assoc_mem.v` with its prototype ROM in block RAM (same as the 4096 "ROM in BRAM" variant).
Prototype/item-memory contents for D<4096 are the head of the 4096 data (resource characterisation only).
Power is the tool's vectorless estimate; "dynamic" is the PL-only dynamic figure.

| Design | D | Clock | LUT | FF | BRAM tiles | DSP | WNS (ns) | Failing endpoints | Dynamic power (W) |
|---|---|---|---|---|---|---|---|---|---|
| Baseline wrapper (submitted, re-run) | 4096 | 1 MHz | 5,321 | 8,760 | 42 | 0 | +986.81 | 0 | 0.001 |
| Baseline wrapper (re-run) | 4096 | 100 MHz | 5,319 | 8,760 | 42 | 0 | +0.379 | 0 | 0.132 |
| Baseline wrapper | 2048 | 1 MHz | 4,565 | 4,216 | 24.5 | 0 | +989.01 | 0 | 0.001 |
| Baseline wrapper | 2048 | 100 MHz | 4,565 | 4,216 | 24.5 | 0 | +2.020 | 0 | 0.096 |
| Baseline wrapper | 1024 | 1 MHz | 4,318 | 2,177 | 18 | 0 | +986.73 | 0 | 0.001 |
| Baseline wrapper | 1024 | 100 MHz | 4,318 | 2,177 | 18 | 0 | +1.935 | 0 | 0.081 |
| Classifier (ROM in BRAM) | 4096 | 1 MHz | 6,250 | 8,884 | 44 | 0 | not recorded here | - | - |
| Classifier (ROM in BRAM) | 4096 | 100 MHz | 6,262 | 8,884 | 44 | 0 | **-0.264** | 19 | 0.140 |
| Classifier (ROM in BRAM) | 2048 | 1 MHz | 4,947 | 4,424 | 26.5 | 0 | +986.82 | 0 | 0.001 |
| Classifier (ROM in BRAM) | 2048 | 100 MHz | 4,954 | 4,424 | 26.5 | 0 | **-0.223** | 15 | 0.108 |
| Classifier (ROM in BRAM) | 1024 | 1 MHz | 4,442 | 2,372 | 20 | 0 | +986.35 | 0 | 0.001 |
| Classifier (ROM in BRAM) | 1024 | 100 MHz | 4,450 | 2,372 | 20 | 0 | **-0.164** | 6 | 0.090 |

## Reading
* The baseline wrapper shrinks with D: LUT 5,319 -> 4,565 -> 4,318 and FF 8,760 -> 4,216 -> 2,177 for D = 4096 -> 2048 -> 1024 (FF about
  halves with D; LUT falls more slowly, since the tokenizer, binder control and 32-bit output path do not scale with D). BRAM 42 -> 24.5 -> 18. DSP stays 0.
* The classifier's added cost (versus the same-D baseline): +132 LUT / +195 FF / +2 BRAM at 1024; +382 LUT / +208 FF / +2 BRAM at 2048;
  +929 LUT / +124 FF / +2 BRAM at 4096 (BRAM ROM variant). The BRAM increment is constant and the LUT increment grows with D; I did not investigate why (the chunk width is fixed at 128, so the
  XOR/popcount does not widen; the query-word mux and the query-side wiring are candidates but unverified).
* **Timing at 100 MHz: the baseline closes at every D (+0.38, +2.02, +1.94 ns); the classifier with BRAM ROM does not (-0.164, -0.223, -0.264 ns; 6, 15, 19
  failing endpoints for D = 1024, 2048, 4096).** Meeting 100 MHz with the classifier would need the ROM read or popcount pipelined further; that was not attempted.
* At the submitted 1 MHz constraint everything meets timing with about 986 ns slack; the 1 MHz dynamic power (0.001 W) is the figure
  the submitted paper reports as 1.0 mW and is not a meaningful power comparison between designs.

## Limits
* All power is a tool estimate; static power (about 0.09 W total on-chip minus dynamic) is device static, not design power.
* The 4096 classifier 1 MHz WNS was not re-extracted for this table (see vivado_delta.md for the 4096 runs).
* ROM/item-memory contents at D<4096 are truncated copies, so these runs characterise resources and timing, not functional behaviour. Functional equivalence of the classifier
  was verified at D=4096 (cocotb) and, for the ASIC streaming variant, at 256/1024/2048.
