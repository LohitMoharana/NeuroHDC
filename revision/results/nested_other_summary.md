# Nested validation: PhysioNet, ST-T, PTB (revision prep; the submitted five-fold numbers stay final)

Outer folds = submitted StratifiedGroupKFold(5, seed 42) by record/file; inner = 3-fold by record on outer-train; candidate 0 = submitted setting, wins ties.
'Baseline' = the submitted setting re-run in this revision folder with the same seeds (not copied from the paper).

| dataset | family | selected per fold (candidate idx) | nested outer macro-F1 mean±std | submitted-setting F1 mean±std | delta | folds with non-default pick |
|---|---|---|---|---|---|---|
| PhysioNet 2017 | rhythm | [1, 1, 1, 1, 1] | 47.58±0.50 | 45.05±0.80 | +2.53 | 5/5 |
| PhysioNet 2017 | schedule | [0, 0, 2, 0, 2] | 45.02±0.79 | 45.05±0.80 | -0.02 | 2/5 |
| PhysioNet 2017 | caps | [3, 3, 3, 3, 3] | 45.49±0.39 | 45.05±0.80 | +0.44 | 5/5 |
| European ST-T | schedule | [4, 1, 4, 4, 2] | 78.12±2.89 | 78.51±3.56 | -0.39 | 5/5 |
| European ST-T | caps | [0, 1, 0, 1, 0] | 77.96±4.02 | 78.51±3.56 | -0.55 | 2/5 |
| PTB | schedule | [4, 2, 4, 4, 2] | 55.93±3.23 | 56.24±3.46 | -0.31 | 5/5 |
| PTB | caps | [0, 2, 0, 2, 2] | 55.81±3.09 | 56.24±3.46 | -0.42 | 3/5 |

A delta within the fold-to-fold std is not evidence of improvement. See gap_closure.md for interpretation.
