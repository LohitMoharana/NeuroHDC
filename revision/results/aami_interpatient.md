# AAMI four-class (N, S, V, F) inter-patient evaluation on MIT-BIH (revision preparation; not in the submitted paper)

Protocol: train on DS1, test on DS2 (De Chazal-style inter-patient paradigm). Record lists verified against Guo et al., arXiv 1810.04121
(22 + 22 records; 102, 104, 107, 217 excluded as paced). Symbol mapping N = N L R e j | S = A a J S | V = V E | F = F | Q (/ f Q) dropped in train and test
(cross-checked against the PhysioNet `AnnotationFilterConvert.m` mapping and Guo et al.; non-beat annotations ignored). Window, tokenizer, D=4096 encoder,
one-shot + 30-epoch refinement and caps (12,000 N / 3,000 others) are the submitted pipeline; **nothing was tuned on DS2**. Script `aami_experiment.py`;
CNN baseline `aami_cnn_baseline.py` (the paper's ECG_1D_CNN, same caps/epochs). The only randomness is training-sample choice and order, so 5 seeds (42..46) are
reported as mean +- std; there is a single fixed train/test split, so these stds are NOT fold-to-fold spreads and are not comparable to the paper's five-fold stds.
Beat counts (this implementation): train N 45,846 / S 944 / V 3,788 / F 414; test N 44,241 / S 1,837 / V 3,220 / F 388.

| Model | Accuracy | Macro-F1 | S sens / PPV / FPR | V sens / PPV / FPR | F sens / PPV |
|---|---|---|---|---|---|
| NeuroHDC, rhythm off | 78.61+-2.65 | 35.51+-4.60 | 13.71 / 12.06 / 2.33 | 74.27 / 29.44 / 13.15 | 1.03 / 0.28 |
| **NeuroHDC, rhythm ON (submitted, whole-record median)** | **85.98+-0.36** | **42.70+-1.12** | 8.15 / 11.63 / 2.28 | 76.81 / 61.39 / 3.39 | 2.16 / 0.42 |
| NeuroHDC, rhythm ON, causal (last <=8 intervals) | 83.78+-1.31 | 42.68+-2.40 | 12.27 / 9.50 / 4.47 | 85.46 / 57.84 / 4.75 | 1.65 / 0.33 |
| 1D-CNN baseline (paper's model, no rhythm) | 76.98+-5.04 | 38.63+-3.28 | 11.68 / 4.73 / 9.48 | 85.43 / 44.57 / 8.45 | 8.25 / 2.68 |

(All values are percentages; sens = sensitivity, PPV = positive predictive value, FPR = false positive rate; per-seed values in `results/aami_*.json`.)

## Published reference (NOT re-run; verify before quoting)
De Chazal et al., IEEE TBME 51(7):1196-1206, 2004 (the 44-record DS1/DS2 design this follows). From a search-result summary of its abstract only (the
paper and abstract pages were not accessible): SVEB sensitivity 75.9%, positive predictivity 38.5%, FPR 4.7% on the independent test set, with hand-crafted
morphology + interval features and a linear discriminant classifier. I did not retrieve its VEB figures and quote none. Those features/preprocessing differ from
NeuroHDC's raw-window encoding, so any comparison must say so.

## Reading (what this does and does not show)
* **NeuroHDC is weak on S and F in this setting.** S sensitivity is 8-14% and F sensitivity about 1-2% against a published SVEB sensitivity of 75.9%. The extremely
  imbalanced, morphologically similar S and F classes are not resolved by the delta-tokenised encoding. This is a real limitation and should be stated, not hidden.
* **Rhythm binding is what makes V usable:** it raises V PPV from 29% to 61% and macro-F1 from 35.5 to 42.7, and the causal R-R variant keeps the macro-F1 (42.68 vs 42.70)
  while shifting the trade-off (V sensitivity 85% but lower PPV, higher S sensitivity). That supports the claim that the rhythm effect survives a causal reference here,
  but it is one split and the stds overlap.
* **The CNN is not stronger overall:** NeuroHDC with rhythm has higher accuracy and macro-F1 (42.7 vs 38.6), but the CNN has no rhythm input, higher V sensitivity and higher F sensitivity. The CNN
  baseline is the paper's small 1D-CNN with 15 epochs, not a tuned model; it is not a "strong baseline" in the literature sense. A stronger baseline (e.g., a published inter-patient model
  re-implemented, or De Chazal's features with a linear classifier) has not been run.
* Overall accuracy is dominated by the N class (about 89% of test beats); macro-F1 and per-class sensitivity are the informative numbers.
* The MIT-BIH 5-class result in the paper (70.99 / 35.77) is on a different label set and 5-fold record-grouped CV and must not be mixed with these numbers.

## Limits
* Single fixed split, one channel (the loader's second CSV column, MLII), annotated R peaks (as submitted), Q dropped.
* R-R intervals here are taken from all real beat annotations including Q (the original loader used only its five kept classes); this changes the median slightly.
* No hyper-parameter was tuned; no re-seeded D < 4096 variant was run on this split.

---
## Added: De Chazal-style classical baselines (aami_classic_baselines.py, results/aami_classic.json) and comparison with NeuroHDC
My re-implementation in the style of De Chazal et al.: 64 down-sampled morphology samples + 7 R-R interval features (pre/post R-R, local and record mean, ratios; post-R-R and the
record mean are non-causal) from one lead (MLII), standardised, same DS1/DS2 split, Q dropped. NOT his published feature set or system.

| Model (percentages) | Accuracy | Macro-F1 | S sens / PPV / FPR | V sens / PPV / FPR | F sens / PPV |
|---|---|---|---|---|---|
| **NeuroHDC, rhythm ON (submitted)** | 85.98+-0.36 | 42.70+-1.12 | 8.15 / 11.63 / 2.28 | 76.81 / 61.39 / 3.39 | 2.16 / 0.42 |
| NeuroHDC, rhythm ON, causal R-R | 83.78+-1.31 | 42.68+-2.40 | 12.27 / 9.50 / 4.47 | 85.46 / 57.84 / 4.75 | 1.65 / 0.33 |
| 1D-CNN (paper's, no rhythm) | 76.98+-5.04 | 38.63+-3.28 | 11.68 / 4.73 / 9.48 | 85.43 / 44.57 / 8.45 | 8.25 / 2.68 |
| LDA, all DS1 beats (De Chazal-style) | 88.53 | 44.58 | 8.22 / 9.51 / 3.00 | 68.26 / 73.91 / 1.67 | 7.73 / 3.03 |
| LDA, 12000/3000 caps (like NeuroHDC) | 88.96+-0.16 | 46.74+-0.29 | 9.17 / 14.08 / 2.16 | 83.39 / 69.91 / 2.49 | 12.89 / 3.33 |
| HistGradientBoosting, all DS1 beats | 92.19+-0.84 | 47.14+-0.62 | 9.96 / 37.33 / 0.65 | 95.09 / 63.47 / 3.83 | 0.15 / 0.25 |

### Reading
* **These baselines are only slightly stronger than NeuroHDC: macro-F1 44.6-47.1 versus 42.7**, and NeuroHDC's V sensitivity/PPV is in the same range as theirs.
  NeuroHDC's rhythm-ON accuracy (86.0) is below the LDA/boosting accuracy (88.5-92.2). So NeuroHDC is competitive with simple classical learners on morphology plus intervals,
  not better than them, on this split.
* **S and F are unsolved by everything I ran.** My De Chazal-style LDA reaches only about 8-9% SVEB sensitivity. **That is far below the 75.9% SVEB sensitivity in De Chazal's
  abstract (as seen in a search summary, not verified at the source), so my re-implementation does NOT reproduce his result** and must not be presented as "De Chazal's
  baseline". The gap shows that his features (two leads, a richer morphology set, his specific selection and thresholding) matter a lot, and a faithful reproduction needs his
  paper's exact feature definitions, which I did not have.
* Because no baseline of mine reaches the published S sensitivity, the honest statement is: NeuroHDC's S/F weakness is shared by simple classifiers built from the same single-lead
  information, and closing it (if a reviewer asks) needs better features or an S-specific design, not a different classifier on the same inputs.
* Accuracy and macro-F1 are dominated by N and by the V class; compare per-class sensitivity/PPV.

### Still not done
* A faithful De Chazal reproduction (his exact features, two leads) and a published deep inter-patient model re-implemented.
* A hardware-cost comparison: the classical baselines use multipliers (LDA/boosting) and were not synthesised.

---
## Attempt at a faithful De Chazal reproduction: DID NOT REPRODUCE (negative result; not a usable baseline)
Source: the full paper (de Chazal, O'Dwyer, Reilly, IEEE TBME 51(7):1196-1206, 2004), read from the PDF the author placed in `Research Papers/`.
Confirmed from it: the DS1/DS2 design (44 non-paced recordings, 22+22), AAMI classes, record-wise cross-validation (DD1), and his reported DS2 result for his
selected configuration IX: SVEB sensitivity 75.9% / PPV 38.5% / FPR 4.7%, VEB 77.7% / 81.9% / 1.2%. My DS1 counts (N 45,854, S 944, V 3,788, F 415) are within 2 beats of
his stated training counts (942 SVEB, 3,787 VEB), so the split and the label mapping agree with his.

Configuration IX needs the Laguna `ecgpuwave` QRS/T-wave segmentation (not available), so it was not attempted. I implemented his fixed-interval configurations
III, VII and XI from the paper (`aami_dechazal_ld.py`: median-filter baseline removal, 12-tap low-pass, 4 R-R features, 10+8 fixed-interval samples per lead, class-weighted
linear discriminants with equal priors, product-of-posteriors across leads). The paper quotes DS1 record-wise CV targets for VII (accuracy 83.0%, SVEB/VEB/F sensitivity
30.4/39.9/32.1) and XI (86.2%, 54.7/40.0/26.0). **My re-implementation does not reach them:**

| DS1 record-wise 22-fold CV | accuracy | S / V / F sensitivity |
|---|---|---|
| paper, configuration VII | 83.0 | 30.4 / 39.9 / 32.1 |
| mine, configuration VII | 45.7 | 21.8 / 30.4 / 26.7 |
| paper, configuration XI | 86.2 | 54.7 / 40.0 / 26.0 |
| mine, configuration XI (weighted LD, equal priors: the paper's stated setting) | 53.5 | 20.0 / 29.3 / 18.6 |
| mine, XI, unweighted, equal priors | 62.5 | 19.8 / 28.6 / 23.6 |
| mine, XI, weighted, empirical priors | 88.3 | 3.7 / 7.3 / 0.0 |
| mine, XI, unweighted, empirical priors | 85.8 | 0.2 / 13.1 / 0.0 |

(`aami_dechazal_variants.py`.) No setting gives both the high accuracy and the balanced minority sensitivities the paper reports. The likely causes are details I do not
have (his exact filter, the segmentation-derived features, how his posteriors/priors were combined, possibly differences between this CSV export of MIT-BIH and the original
signals, e.g. lead-B assignment per record), not a verified bug. DS2 results of this implementation are in `results/aami_dechazal_ld.json` and must not be quoted as a De Chazal result.
Consequence: the only baselines usable for comparison are the ones already reported above, which are labelled as my own re-implementations; De Chazal's published figures can be cited as
published numbers only.
