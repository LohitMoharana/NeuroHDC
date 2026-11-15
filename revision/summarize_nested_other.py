"""Summarise nested-validation results for PhysioNet (rhythm/schedule/caps), ST-T and PTB (schedule/caps) against the
non-nested fold F1 of the submitted setting (re-run here with identical seeds). Writes results/nested_other_summary.md"""
import json, glob, os, numpy as np
R = os.path.join(os.path.dirname(__file__), "results")
base = {"pn": json.load(open(f"{R}/physionet_whole.json"))["fold_f1"],
        "stt": json.load(open(f"{R}/stt_subject_group.json"))[0]["fold_f1"],
        "ptb": json.load(open(f"{R}/ptb_patient_group.json"))[0]["fold_f1"]}
names = {"pn": "PhysioNet 2017", "stt": "European ST-T", "ptb": "PTB"}
out = ["# Nested validation: PhysioNet, ST-T, PTB (revision prep; the submitted five-fold numbers stay final)\n",
       "Outer folds = submitted StratifiedGroupKFold(5, seed 42) by record/file; inner = 3-fold by record on outer-train; candidate 0 = submitted setting, wins ties.",
       "'Baseline' = the submitted setting re-run in this revision folder with the same seeds (not copied from the paper).\n",
       "| dataset | family | selected per fold (candidate idx) | nested outer macro-F1 mean±std | submitted-setting F1 mean±std | delta | folds with non-default pick |", "|---|---|---|---|---|---|---|"]
for ds in ("pn", "stt", "ptb"):
    for fam in ("rhythm", "schedule", "caps"):
        fs = sorted(glob.glob(f"{R}/nested_{ds}_{fam}_f*.json"))
        if len(fs) != 5: continue
        res = [json.load(open(f)) for f in fs]
        f1 = np.array([r["outer_macro_f1"] for r in res]); b = np.array(base[ds])
        sel = [r["selected"] for r in res]
        out.append(f"| {names[ds]} | {fam} | {sel} | {f1.mean():.2f}±{f1.std():.2f} | {b.mean():.2f}±{b.std():.2f} | {f1.mean()-b.mean():+.2f} | {sum(s != 0 for s in sel)}/5 |")
out.append("\nA delta within the fold-to-fold std is not evidence of improvement. See gap_closure.md for interpretation.")
open(f"{R}/nested_other_summary.md", "w").write("\n".join(out) + "\n"); print("\n".join(out))
