| family | acc mean±sd | macro-F1 mean±sd | ΔF1 vs submitted per fold | ΔF1 mean | ΔAcc mean | folds F1 up | folds w/ non-baseline pick |
|---|---|---|---|---|---|---|---|
| schedule | 71.37±5.98 | 36.91±7.01 | +1.11 +2.08 +0.00 +3.56 -1.07 | +1.14 | +0.38 | 3/5 | 4/5 |
| caps | 71.13±6.10 | 38.05±7.36 | +0.00 +4.06 +0.00 +7.32 +0.00 | +2.28 | +0.14 | 2/5 | 2/5 |
| rhythm | 71.82±6.52 | 38.09±9.14 | +0.00 +1.18 +0.00 +10.38 +0.00 | +2.31 | +0.83 | 2/5 | 2/5 |
| tokenizer | 70.69±10.00 | 38.18±7.34 | +0.00 +4.52 -1.79 +6.15 +3.14 | +2.41 | -0.30 | 3/5 | 4/5 |

Per-fold selections (inner mean macro-F1 of winner vs submitted setting; outer test acc/F1):
- schedule f1: picked {'lr0': 5}; inner 36.76 vs submitted 36.48 (inner gain +0.28); outer acc 73.20, F1 42.37 (submitted fold F1 41.26, delta +1.11)
- schedule f2: picked {'lr0': 30}; inner 44.23 vs submitted 42.84 (inner gain +1.39); outer acc 63.81, F1 25.73 (submitted fold F1 23.66, delta +2.08)
- schedule f3: picked submitted; inner 32.59 vs submitted 32.59 (inner gain +0.00); outer acc 66.67, F1 33.25 (submitted fold F1 33.25, delta +0.00)
- schedule f4: picked {'lr0': 5}; inner 36.78 vs submitted 35.87 (inner gain +0.91); outer acc 81.15, F1 45.71 (submitted fold F1 42.15, delta +3.56)
- schedule f5: picked {'epochs': 60}; inner 39.14 vs submitted 37.46 (inner gain +1.68); outer acc 72.01, F1 37.47 (submitted fold F1 38.54, delta -1.07)
- caps f1: picked submitted; inner 36.48 vs submitted 36.48 (inner gain +0.00); outer acc 73.59, F1 41.26 (submitted fold F1 41.26, delta +0.00)
- caps f2: picked {'cap_a': 6000}; inner 43.32 vs submitted 42.84 (inner gain +0.48); outer acc 63.92, F1 27.72 (submitted fold F1 23.66, delta +4.06)
- caps f3: picked submitted; inner 32.59 vs submitted 32.59 (inner gain +0.00); outer acc 66.67, F1 33.25 (submitted fold F1 33.25, delta +0.00)
- caps f4: picked {'cap_a': 6000}; inner 37.10 vs submitted 35.87 (inner gain +1.22); outer acc 81.45, F1 49.48 (submitted fold F1 42.15, delta +7.32)
- caps f5: picked submitted; inner 37.46 vs submitted 37.46 (inner gain +0.00); outer acc 70.01, F1 38.54 (submitted fold F1 38.54, delta +0.00)
- rhythm f1: picked submitted; inner 36.48 vs submitted 36.48 (inner gain +0.00); outer acc 73.59, F1 41.26 (submitted fold F1 41.26, delta +0.00)
- rhythm f2: picked {'short': 0.8, 'long': 1.2}; inner 43.21 vs submitted 42.84 (inner gain +0.37); outer acc 65.28, F1 24.84 (submitted fold F1 23.66, delta +1.18)
- rhythm f3: picked submitted; inner 32.59 vs submitted 32.59 (inner gain +0.00); outer acc 66.67, F1 33.25 (submitted fold F1 33.25, delta +0.00)
- rhythm f4: picked {'short': 0.8, 'long': 1.2}; inner 35.94 vs submitted 35.87 (inner gain +0.07); outer acc 83.52, F1 52.53 (submitted fold F1 42.15, delta +10.38)
- rhythm f5: picked submitted; inner 37.46 vs submitted 37.46 (inner gain +0.00); outer acc 70.01, F1 38.54 (submitted fold F1 38.54, delta +0.00)
- tokenizer f1: picked submitted; inner 36.48 vs submitted 36.48 (inner gain +0.00); outer acc 73.59, F1 41.26 (submitted fold F1 41.26, delta +0.00)
- tokenizer f2: picked {'tok': 't_mid'}; inner 43.20 vs submitted 42.84 (inner gain +0.36); outer acc 65.84, F1 28.18 (submitted fold F1 23.66, delta +4.52)
- tokenizer f3: picked {'tok': 't_wide'}; inner 34.45 vs submitted 32.59 (inner gain +1.86); outer acc 54.21, F1 31.47 (submitted fold F1 33.25, delta -1.79)
- tokenizer f4: picked {'tok': 't_lo'}; inner 36.33 vs submitted 35.87 (inner gain +0.46); outer acc 83.58, F1 48.31 (submitted fold F1 42.15, delta +6.15)
- tokenizer f5: picked {'tok': 't_lo'}; inner 41.88 vs submitted 37.46 (inner gain +4.42); outer acc 76.20, F1 41.68 (submitted fold F1 38.54, delta +3.14)