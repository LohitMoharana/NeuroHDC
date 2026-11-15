# OpenLane 1.0.2, sky130A / sky130_fd_sc_hd, scaled 256-bit prototype (WINDOW_SIZE=32, CHUNK=32, FOLDS=8), CLOCK_PERIOD 50 ns (20 MHz)
Same config.json for both runs (copy of ~/OpenLane/designs/neurohdc/config.json); runs RUN_REV_BASE / RUN_REV_CLS in new design folders.
| metric | baseline re-run | previous 2026.08.30 run | + streaming classifier | delta (cls vs base) |
|---|---|---|---|---|
| synth cells | 13,007 | 13,007 | 14,969 | +1,962 (+15.1%) |
| total cells (incl. fill/tap) | 66,589 | 66,589 | 75,573 | +8,984 |
| die area (mm2) | 0.620 | 0.620 | 0.677 | +0.054 (+9.1%) |
| critical path (ns) | 3.96 | 3.96 | 5.16 | +1.20 |
| setup / hold worst slack (ns) | 37.05 / 0.31 | 37.05 / 0.31 | 35.92 / 0.30 | -1.13 / -0.01 |
| power typ, tool estimate (mW) | 19.68 | 19.68 | 26.40 | +6.72 (+34%) |
| DRC / LVS errors | 0 / 0 | 0 / 0 | 0 / 0 | |
| antenna violators (pins / nets) | 50 / 44 | 50 / 44 | 65 / 56 | +15 / +12 |
| max slew / fanout violations | 0 / 1 | 0 / 1 | 21 / 1 | +21 slew |
| runtime | 11m39s | 9m50s | 13m49s | |
Baseline re-run is metric-for-metric identical to the earlier run (flow reproducible).
Caveats: power is the flow's default-activity estimate, not vector-based; ROM holds first 256 bits of trained prototypes only to make it non-trivial (encoder in this prototype is not the trained D=4096 model); no memory macros.
Raw: revision/results/asic_comparison_raw.txt

## Addendum (2026-11-14)
- Slew fix: GLB_/PL_RESIZER_MAX_SLEW_MARGIN=30 -> 0 slew violations (was 21); cells/area/timing identical; power 26.5 mW; antenna 53/47. See gap_closure.md.
- Full D=4096 attempt failed in global routing (GRT-0119 congestion). See gap_closure.md section 6.

---
## Full D=4096 attempt (not closed)
See gap_closure.md "Full D=4096 ASIC attempt: final outcome". Four OpenLane attempts; none reached signoff. No area,
power, timing, DRC or LVS figures exist for the full design. Last state: detailed routing first pass at 100% with
219,641 violations (RUN_C, congestion override on), then the WSL VM restarted. Configs and logs are under
asic/openlane_configs/4096/ and asic/openlane_logs/.
