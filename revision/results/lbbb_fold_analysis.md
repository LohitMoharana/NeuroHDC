Records containing each class (whole dataset): Normal: 40 records / 75021 beats; PVC: 37 records / 7129 beats; PAC: 27 records / 2546 beats; LBBB: 4 records / 8071 beats; RBBB: 6 records / 7256 beats

| fold | test records w/ LBBB (beats) | LBBB beats in TRAIN | fold F1 (acc) | LBBB F1 | PAC F1 | PVC F1 | RBBB F1 |
|---|---|---|---|---|---|---|---|
| 1 | 0 (0) [] | 8071 | 41.26 (73.59) | 0.00 | 1.08 | 39.05 | 82.13 |
| 2 | 1 (2490) [np.str_('109')] | 5581 | 23.66 (63.97) | 1.83 | 0.62 | 30.74 | 2.05 |
| 3 | 1 (2001) [np.str_('214')] | 6070 | 33.25 (66.67) | 0.00 | 4.16 | 62.37 | 17.42 |
| 4 | 1 (1457) [np.str_('207')] | 6614 | 42.15 (80.70) | 0.00 | 9.06 | 79.26 | 29.77 |
| 5 | 1 (2123) [np.str_('111')] | 5948 | 38.54 (70.01) | 2.69 | 51.40 | 54.24 | 0.00 |