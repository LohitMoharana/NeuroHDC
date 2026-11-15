# Gap closure (2026-11-14) - revision preparation only; submitted manuscript/numbers untouched

## 1. Vivado at a realistic clock (weakness: submitted power/timing are at 1 MHz)
Committed constraints.xdc declares create_clock -period 1000 (1 MHz) although its comment says 100 MHz.
| run (Vivado 2022.2, xc7z010clg225-3, OOC) | clock | LUT | FF | BRAM | DSP | WNS (ns) | dynamic power (tool, vectorless) |
|---|---|---|---|---|---|---|---|
| baseline top_shde_wrapper | 1 MHz | 5321 | 8760 | 42 | 0 | 986.810 | 0.001 W |
| baseline | 100 MHz | 5319 | 8760 | 42 | 0 | +0.379 | **0.132 W** |
| classifier, ROM in LUTs | 1 MHz | 7268 | 9130 | 42 | 0 | 986.... | 0.001 W |
| classifier, ROM in LUTs | 100 MHz | 7272 | 9130 | 42 | 0 | +0.229 | 0.147 W |
| classifier, ROM in BRAM (read reg moved out of async-reset block) | 1 MHz | 6250 | 8884 | 44 | 0 | 986.568 | 0.001 W |
| classifier, ROM in BRAM | 100 MHz | 6262 | 8884 | 44 | 0 | **-0.264 (19 failing endpoints)** | 0.140 W |
Reports: revision/vivado/out_extra_runs/, out_classifier_final/, out_baseline/.

## 2. ASIC slew violations (classifier run had 21)
Config-only change GLB_RESIZER_MAX_SLEW_MARGIN=PL_RESIZER_MAX_SLEW_MARGIN=30 -> 0 slew violations; cells/area/timing unchanged
(synth cells 14969, die 0.677 mm2, critical path 5.16 ns, setup/hold 35.92/0.30), power 26.5 mW (tool), antenna 53/47 (was 65/56), DRC 0, LVS 0.

## 3. LBBB failure (weakness 2): see lbbb_fold_analysis.md
Only 4 LBBB records (109,111,207,214) / 8071 beats; each is the sole LBBB test record in one fold; fold 1 has no LBBB test beats at all
yet macro-F1 still counts LBBB (predicted but absent -> F1 0). LBBB F1 is 0-2.7 in every fold.

## 4. PhysioNet rhythm (weakness 5 on PhysioNet), paper protocol, 5 folds seed 42, F1 excludes Noisy
| variant | acc | macro-F1 |
|---|---|---|
| rhythm off | 58.51±0.59 | 47.58±0.50 |
| whole-record median (submitted) | 56.88±0.62 | 45.05±0.80 |
| causal (preceding intervals) | 56.11±0.42 | 44.63±0.36 |
| causal-8 | 56.51±0.50 | 45.05±0.70 |
Submitted numbers reproduced exactly (45.05; rhythm effect -2.53). Causal medians do not change the picture; rhythm binding hurts PhysioNet in every form.

## 5. PTB grouping (weakness 7)
Patient list: PhysioNet ptbdb RECORDS (549 records, 290 patients, all 549 CSVs matched; revision/data_external/ptbdb_RECORDS.txt).
| grouping | acc | macro-F1 | patients in both train and test (per fold) |
|---|---|---|---|
| file name (as submitted) | 90.06±1.04 | 56.24±3.46 (reproduces submitted) | 60,61,60,53,59 |
| patient | 90.09±2.15 | **51.02±2.25** | 0,0,0,0,0 |
ST-T (European ST-T DB): record-to-subject map not available offline; NOT checked.

## Not closed
Related work (needs PDF text extraction / your literature choices; no PDF reader installed here), ST-T subject grouping, gate-level ASIC verification.

## 6. Full D=4096 ASIC attempt (OpenLane 1.0.2, sky130A, 50 ns, same config as the scaled runs, no memory macros)
Design: top_shde_wrapper4096_cls = prototype core at CHUNK=128/FOLDS=32/WINDOW=256 + 32-entry chunk FIFO + 32-bit serialiser + streaming
associative memory with the full trained 4096-bit prototypes. RTL simulation: 4 windows, 128 chunks, 0 mismatches vs Python.
Result: **flow failed** at global-routing resizer (step 15): `[ERROR GRT-0119] Routing congestion too high` after 42m53s.
Reached before failing: synth cells 174,444 (34,103 MUX, 6,465 XOR, 1,576 XNOR), total cells 344,223, die 7.83 mm2 at 25% utilisation.
(scaled 256-bit classifier run: 14,969 synth cells, 0.677 mm2.) No signoff numbers exist for the full-size design.
Not tried: lower utilisation / congestion-related config, or an RTL change to the accumulator read mux (32:1 x 1024 bits) that dominates the MUX count.

---
## Added in this session (second gap-closure pass)

### Related work (see related_work_notes.md)
Full text of all 9 PDFs in `Research Papers/` was extracted and searched. None of the five application papers
(CLDV, HDDSNN, HyperGRAF, MTSA, SpikeHD) mentions ECG or arrhythmia. No ECG-specific HDC baseline exists in the
folder; none was added from memory. CLDV Table I shows prior art for sparsity, MAC-free arithmetic and chunked
hypervector datapaths, so novelty should be phrased as the ECG combination with the measured FPGA/ASIC flow.

### ST-T subject grouping (stt_subject_group.py, results/stt_subject_group.json)
No official record-to-subject mapping is available offline; the PhysioNet header comments (age, sex, diagnosis,
medication) were used as a proxy signature: 90 records -> 80 signature groups; 7 signatures are shared by 2-4 records.
Record grouping (as submitted): macro-F1 78.51±3.56 (submitted 78.48±2.46; the loader's beat sampling uses the
global RNG which the submitted script does not seed, so I seeded it at 42 -> same mean, different spread);
2-4 signature groups straddle train/test per fold. Signature grouping (no straddling): 76.16±6.67 (-2.35, inside
fold noise). This is a proxy, not a verified subject mapping.

### Gate-level verification of the scaled classifier (asic/tb/test_gl_trace.py, run_gl_trace.py)
The synthesised sky130 netlist of the scaled classifier (RUN_REV_CLS, results/final/verilog/gl/
top_shde_wrapper_cls.nl.v, sha256 8696a4a205e8fce52042ea9b1ba24ea99163da30c2a0dba022a81c9ac210c82e; PDK models
sky130_fd_sc_hd.v + primitives.v) was simulated with Icarus (functional, zero delay) against the RTL with an identical
port-only stimulus (12 windows after the prime-and-reset prologue). Result: class_valid results (12) and hv_valid_out
words (96) are cycle-identical between RTL and gate level, no X/Z in the gate-level outputs. Limits: functional only
(no SDF timing), 12 windows, only 9 distinct hv words, only the scaled 256-bit prototype (not the 4096 design), and
the baseline (no classifier) netlist was not simulated.

### Nested validation beyond MIT-BIH (nested_physionet.py, nested_generic.py, results/nested_other_summary.md)
| dataset | family | nested outer F1 | submitted-setting F1 | delta |
|---|---|---|---|---|
| PhysioNet | rhythm | 47.58±0.50 (rhythm OFF chosen in 5/5 folds) | 45.05±0.80 | +2.53 |
| PhysioNet | schedule | 45.02±0.79 | 45.05±0.80 | -0.02 |
| PhysioNet | caps | 45.49±0.39 (cap_a=6000 chosen 5/5) | 45.05±0.80 | +0.44 |
| ST-T | schedule | 78.12±2.89 | 78.51±3.56 | -0.39 |
| ST-T | caps | 77.96±4.02 | 78.51±3.56 | -0.55 |
| PTB | schedule | 55.93±3.23 | 56.24±3.46 | -0.31 |
| PTB | caps | 55.81±3.09 | 56.24±3.46 | -0.42 |
Reading: inner-CV selection never beats the submitted setting outside noise on ST-T or PTB. On PhysioNet it
re-discovers, without touching the test fold, that the rhythm binding hurts (+2.53 when off), consistent with the
submitted -2.53 PhysioNet rhythm effect. Tokenizer family was not run for these datasets (no cached tokenizations).

### ST-T subject grouping, updated with the OFFICIAL mapping (replaces the header proxy as the reference)
The PhysioNet page for the European ST-T database (https://physionet.org/content/edb/1.0.0/) states 90 records from
79 subjects and lists the same-subject records: e0118-e0122, e0123-e0126, e0129+e0133, e0136+e0139, e0147+e0148,
e0154+e0155, e0162+e0163 (no e0120 file exists). Verified by fetching the raw page text and checking the files on disk.
Re-run (stt_subject_group.py): record grouping (submitted) 78.51+-3.56; official subject grouping 77.04+-4.21
(-1.47, inside fold noise; 0 subjects straddle train/test); header proxy 76.16+-6.67 (the proxy missed e0126).

### ECG-specific HDC prior art
See related_work_notes.md (second half). Found: Xu and Parhi 2024, Ung/Ge/Parhi 2022, and ECG-LDC (closest FPGA
competitor; its MIT-BIH result uses a random beat-level split so it is not comparable to NeuroHDC's record-grouped numbers).
Sources were fetched pages or search summaries, not full-text reads.

---
## Full D=4096 ASIC attempt: final outcome (DID NOT CLOSE)

Design: `top_shde_wrapper4096_cls` (core at CHUNK=128, FOLDS=32, WINDOW=256, 32-entry chunk FIFO, 4-word serialiser,
streaming associative memory with constant prototype ROM, no memory macros), OpenLane 1.0.2 / sky130A / sky130_fd_sc_hd,
50 ns clock. Configs: `asic/openlane_configs/4096/`; logs: `asic/openlane_logs/`.

| Attempt | Change from the previous | Result |
|---|---|---|
| 1 `neurohdc_4096` | FP_CORE_UTIL 25, PL_TARGET_DENSITY 0.3 (174,444 synth cells; 344,223 cells total; 7.83 mm2 die) | Failed in global routing (step 15) with GRT-0119 "routing congestion too high" after 42m53s |
| 2 `neurohdc_4096_spread` | FP_CORE_UTIL 12, PL_TARGET_DENSITY 0.15 (die 4025 x 4036 um) | Reached global routing antenna repair; openroad killed by the Linux OOM killer at about 9.4 GB (WSL had 11.4 GB) |
| 3 `neurohdc_4096_allowcong` (RUN_B) | GRT_ALLOW_CONGESTION=1, utilisation as attempt 1 | Global routing finished with overflow (GRT-0115); openroad OOM-killed at about 11.1 GB in antenna repair |
| 4 same config (RUN_C) | WSL memory raised to 20 GB RAM + 8 GB swap (.wslconfig) | Global routing, netlist write, STA and fill completed. Detailed routing (step 23) first pass reached 100% with **219,641 violations** (0 at 20%, 59,747 at 30%, 115,853 at 60%, 168,915 at 80%) after 1h12m. The WSL VM then restarted (uptime 0 min, journal "uncleanly shut down"), killing the container. The repair iterations, signoff DRC/LVS/antenna, final STA and power never ran. |

Facts that can be stated: the design synthesises, floorplans, places, builds a clock tree and global-routes with the
congestion override; detailed routing did not converge in its first pass; there is no DRC, LVS, timing or power result
for the full 4096-bit design.
Facts that cannot be stated: any area/power/Fmax of the full design. The final cause of the VM restart is unknown
(memory pressure with a 20 GB VM, full swap and about 3 GB left for Windows is the likely trigger, not verified).
Do not quote any 4096 ASIC figure in the paper; the scaled 256-bit prototype stays the only closed ASIC datapoint.
Side effect: C:\Users\lohit\.wslconfig was created (memory=20GB, swap=8GB); delete it and run `wsl --shutdown` to undo.

---
## Scaling runs added after the failed 4096 attempts (see asic_scaling.md)
D=1024 and D=2048 versions of the classifier wrapper (CHUNK=128, FOLDS=8/16) closed in OpenLane with 0 detailed-routing
violations, 0 Magic DRC, 0 LVS errors; they still carry antenna and max-slew violations (not fixed). Power (tool est.): 125 mW
and 247 mW. Accuracy on MIT-BIH is flat from D=4096 to D=1024 under the truncation proxy (70.99 / 70.13 / 70.15).
The full 4096 design remains unclosed.

---
## Vivado scaling at D=1024 and 2048 (see vivado_dim.md)
Baseline wrapper: 5,319 / 4,565 / 4,318 LUT, 8,760 / 4,216 / 2,177 FF, 42 / 24.5 / 18 BRAM for D = 4096 / 2048 / 1024 (0 DSP).
The classifier (BRAM ROM) adds +132/+382/+929 LUT and +2 BRAM and does not meet 100 MHz at any D (WNS -0.16 / -0.22 / -0.26 ns); the
baseline meets 100 MHz at every D.
