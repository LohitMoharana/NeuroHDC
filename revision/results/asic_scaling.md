# ASIC datapath scaling: D = 256, 1024, 2048 (closed) and 4096 (did not close)

Flow: OpenLane 1.0.2, sky130A / sky130_fd_sc_hd, 50 ns clock constraint, FP_CORE_UTIL 25, PL_TARGET_DENSITY 0.3, no memory
macros, prototype ROM as constant logic. Revision-prep designs (`asic/rtl/`), NOT the submitted RTL. All power values are
OpenSTA typical-corner tool estimates, not measurements. Configs: `asic/openlane_configs/`; reports: `asic/openlane_reports/`.

| Design | Dimension | Synth cells | Die area (mm2) | Typical power (mW, tool est.) | Detailed-route violations | Magic DRC | LVS errors | Setup WNS / hold worst slack (ns) | Slew / fanout / cap violations | Antenna pin / net | Run time | Peak memory |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Scaled baseline (no classifier, submitted core) | 256 | 13,007 | 0.620 | 19.68 | 0 | 0 | 0 | see asic_delta.md | see asic_delta.md | see asic_delta.md | - | - |
| Scaled + classifier | 256 | 14,969 | 0.677 | 26.4 | 0 | 0 | 0 | see asic_delta.md | 21 slew before slew-margin fix (0 after) | see asic_delta.md | - | - |
| Scaled + classifier | **1024** | 55,870 | 2.475 | **125** (sequential 14.3, combinational 110) | 0 | 0 | 0 | 0.00 / +0.26 (setup worst slack +33.99) | 620 / 15 / 0 | 496 / 353 | 0h49m | 7.1 GB |
| Scaled + classifier | **1024 + slew margin 30** | 55,870 | 2.475 | **125** (sequential/comb. unchanged) | 0 | 0 | 0 | 0.00 / +0.26 (setup worst slack +33.94) | **95** / 8 / 0 | 560 / 392 | 0h47m | 7.1 GB |
| Scaled + classifier | **2048** | 93,530 | 4.163 | **247** (sequential 27.9, combinational 219) | 0 | 0 | 0 | 0.00 / +0.32 (setup worst slack +31.65) | 2,056 / 15 / 1 | 1,366 / 818 | 1h44m | 12.3 GB |
| Scaled + classifier | **2048 + slew margin 30** | 93,530 | 4.163 | **248** (tool est.) | 0 | 0 | 0 | 0.00 / +0.32 (setup worst slack +31.59) | **61** / 7 / 0 | 1,332 / 857 | 1h52m | 12.6 GB |
| Scaled + classifier | 4096 | 174,444 | 7.83 (first attempt) | none | did not converge (see below) | not run | not run | not run | not run | not run | - | >19 GB |

(256-bit figures are those recorded in asic_delta.md; the per-check detail for the 256 rows lives there.)

## What this shows
* Cells, area and power grow roughly linearly with D: synth cells 14,969 -> 55,870 -> 93,530 for D = 256 -> 1024 -> 2048,
  and typical power 26.4 -> 125 -> 247 mW (about 4.7x and 9.4x for 4x and 8x the dimension).
* The 1024 and 2048 designs close in this flow: detailed routing reaches 0 violations, Magic DRC reports 0, LVS reports
  0 errors. The two runs repeat the same pattern (first pass 18.6k / 72.6k violations, then repair iterations to 0).
* 4096 did not close in four attempts (see gap_closure.md): congestion abort, two out-of-memory kills, and a first-pass
  count of 219,641 violations before the WSL VM restarted. Memory demand grew with design size (7.1 GB at 1024,
  12.3 GB at 2048, more than 19 GB at 4096), so on this 20 GB WSL allocation 4096 is not routable in this flow.

## Limits (do not drop these when quoting)
* Both closed runs still have **antenna violations (496/353 and 1,366/818)** and **max-slew violations (620 and 2,056)**; the
  scaled 256-bit classifier needed a resizer slew-margin fix to clear its slew violations. These two runs did not get that
  fix, so they are routed and DRC/LVS clean but not fully electrically clean. Setup timing at a 50 ns constraint is
  met with large slack; this is not a frequency characterisation.
* KLayout and CVC checks are reported as -1 (not run) in metrics.csv.
* Power is a tool estimate with default activity; no measurement exists.
* Functional equivalence of the 1024/2048 RTL to the Python associative-memory model was simulated (4 windows each, 0
  mismatches). Gate-level simulation was done only for the 256-bit design.
* Dimension 1024/2048 prototype ROM contents are the first N bits of the trained 4096-bit prototypes (datapath
  characterisation, not a retrained model).

## Accuracy vs dimension (MIT-BIH, submitted protocol, rhythm ON; revision/dim_accuracy.py)
Cached D=4096 hypervectors truncated to the first N bits (valid because dimensions are generated independently; not a
re-seeded re-encode). N=4096 reproduces the submitted result exactly.
| D | Accuracy | Macro-F1 |
|---|---|---|
| 4096 | 70.99+-5.83 | 35.77+-6.81 |
| 2048 | 70.13+-5.26 | 36.24+-5.93 |
| 1024 | 70.15+-5.96 | 35.87+-7.51 |
Differences are far inside the fold-to-fold spread. MIT-BIH only; PhysioNet, PTB and ST-T were not tested.

## 1024 with the slew-margin fix (LOCKED, run RUN_S1024, config asic/openlane_configs/neurohdc_1024_slew.config.json)
Only change from the closed 1024 run: PL_RESIZER_MAX_SLEW_MARGIN = GLB_RESIZER_MAX_SLEW_MARGIN = 30 (the setting that cleared
the 256-bit classifier's slew violations). Results: flow completed in 47m16s; detailed routing 0 violations; Magic DRC 0;
LVS 0 errors; setup WNS 0.00 (worst slack +33.94 ns at the 50 ns constraint), hold worst slack +0.26 ns; max-slew violations
620 -> 95 (not zero), max-fanout 15 -> 8, max-cap 0; antenna 496/353 -> 560/392 (not improved, slightly worse: the slew margin
does not target antennas); typical power 0.125 W (tool estimate), unchanged; 55,870 synthesised cells, 2.47 mm2 die, peak
memory 7.1 GB. Final GDS sha256 9b524a6cf8a7d3f70642feb11b25fff4a3f0331709e31fbdb1792dd2b283cb21. KLayout and CVC checks
show -1 (not run) in metrics.csv. Reports: asic/openlane_reports/1024_slew/.

## Accuracy vs dimension on all four datasets (truncation proxy; macro-F1, acc in brackets; mean+-std over the 5 submitted folds)
| Dataset | D=4096 (reproduces re-run baseline) | D=2048 | D=1024 |
|---|---|---|---|
| MIT-BIH | 35.77+-6.81 (acc 70.99+-5.83) | 36.24+-5.93 (acc 70.13+-5.26) | 35.87+-7.51 (acc 70.15+-5.96) |
| PhysioNet 2017 | 45.05+-0.80 (acc 56.88+-0.62) | 43.57+-0.89 (acc 56.64+-0.72) | 40.52+-1.73 (acc 54.60+-0.78) |
| PTB | 56.24+-3.46 (acc 90.06+-1.04) | 55.68+-3.21 (acc 89.68+-1.10) | 55.02+-3.22 (acc 88.92+-1.74) |
| European ST-T | 78.51+-3.56 (acc 85.21+-2.51) | 78.14+-3.27 (acc 84.93+-2.02) | 78.13+-3.40 (acc 85.04+-2.17) |

Reading (do not over-claim):
* D=4096 reproduces the re-run baselines exactly (MIT-BIH 35.77, PhysioNet 45.05, PTB 56.24, ST-T 78.51), so the harness is sound.
* MIT-BIH, PTB and ST-T: 2048 and 1024 are within fold noise of 4096 (largest gap -1.2 F1 on PTB, std about 3).
* **PhysioNet 2017 is the exception: macro-F1 falls 45.05 -> 43.57 at 2048 (-1.5, about 2 std) and -> 40.52 at 1024 (-4.5, well outside
  noise).** The three-class AFib task with rhythm binding needs more dimensions than the beat-level tasks.
* So "2048 performs close to 4096" holds for three of four datasets and costs about 1.5 F1 on PhysioNet. It is a truncation proxy
  (first N bits of the cached 4096-bit hypervectors, rhythm codebook redrawn at size N), not a re-seeded re-encode.

## Accuracy vs dimension: RE-SEEDED re-encode (final) vs truncation proxy (macro-F1 mean+-std over the 5 submitted folds)
Re-seeded = every dataset re-encoded with the unchanged encoder at D=N (`SHDEConfig.D=N`, same seed 42; `*_dim.py` builders, `dim_accuracy*_native.py`).

| Dataset | 4096 (submitted setting, re-run) | 2048 re-seeded | 2048 truncated | 1024 re-seeded | 1024 truncated |
|---|---|---|---|---|---|
| MIT-BIH | 35.77+-6.81 | 36.79+-8.06 | 36.24+-5.93 | 37.74+-6.17 | 35.87+-7.51 |
| PhysioNet 2017 | 45.05+-0.80 | 43.90+-0.42 | 43.57+-0.89 | 41.57+-0.44 | 40.52+-1.73 |
| PTB | 56.24+-3.46 | 56.96+-4.25 | 55.68+-3.21 | 56.01+-2.26 | 55.02+-3.22 |
| European ST-T | 78.51+-3.56 | 77.80+-2.37 | 78.14+-3.27 | 77.00+-2.83 | 78.13+-3.40 |

Accuracy (re-seeded): MIT-BIH 71.29+-5.91 (1024) / 70.33+-7.08 (2048); PhysioNet 55.40+-0.79 / 55.58+-0.97; PTB 89.62+-0.67 / 90.03+-1.69;
ST-T 84.31+-1.82 / 84.77+-1.17 (4096: 70.99, 56.88, 90.06, 85.21).

Reading:
* The re-seeded runs agree with the truncation proxy on every dataset to within fold noise, so the earlier conclusion stands without the proxy caveat.
* MIT-BIH, PTB, ST-T: 2048 and 1024 are within fold noise of 4096 (MIT-BIH re-seeded is nominally higher, +1.0 / +2.0 F1, with std 6-8; do not read that as an improvement).
* PhysioNet 2017 degrades with dimension: 45.05 (4096) -> 43.90 (2048, -1.15) -> 41.57 (1024, -3.48), with fold std about 0.4-0.8, so the 1024 loss is clearly
  outside noise and the 2048 loss is about 1.5-2 std.
* Re-seeded 2048 is the best trade-off point in this data, but 4096 remains the submitted design point; the paper's headline numbers are unchanged.

## 2048 with the slew-margin fix (LOCKED, run RUN_S2048, config asic/openlane_configs/neurohdc_2048_slew.config.json)
Same single change as the 1024 fix (PL_/GLB_RESIZER_MAX_SLEW_MARGIN = 30). Flow completed in 1h51m34s (peak memory 12.6 GB); detailed routing 0 violations;
Magic DRC 0; LVS 0 errors; setup WNS 0.00 (worst slack +31.59 ns at the 50 ns constraint), hold worst slack +0.32 ns; max-slew violations 2,056 -> 61, max-fanout 15 -> 7,
max-cap 1 -> 0; antenna 1,366/818 -> 1,332/857 (not improved); typical power 0.248 W (tool estimate; 0.247 W before); 93,530 synthesised cells, 4.16 mm2 die.
Final GDS sha256 5f6769341093311ffc253ee708e016fcf4cb5f807245d37d27a702304ad8fd51. KLayout and CVC checks show -1 (not run). Reports: asic/openlane_reports/2048_slew/.
Net: the slew fix removes about 97% of the 2048 slew violations (about 85% at 1024) but not all, and does not address the antenna violations.
