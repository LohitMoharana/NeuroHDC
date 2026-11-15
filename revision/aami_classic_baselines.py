"""De Chazal-STYLE classical baselines on the AAMI four-class inter-patient split (DS1 train / DS2 test) used by aami_experiment.py.
This is MY re-implementation in the style of De Chazal et al. 2004 (hand-crafted morphology + heartbeat-interval features, linear
discriminant classifier), NOT his published system: the feature definitions below are mine, single channel (MLII), annotated R peaks.
Features per beat:
  morphology : the same 256-sample normalised window as NeuroHDC, down-sampled by 4 -> 64 values
  intervals  : RR_pre, RR_post (non-causal: uses the next beat), mean RR of the 10 preceding beats, whole-record mean RR (non-causal),
               RR_pre/record-mean, RR_post/record-mean, RR_pre/local-mean   (7 values; beats at record edges use the available neighbour/NaN->record mean)
Classifiers (sklearn): LDA (all DS1 beats), LDA (same 12000/3000 caps as NeuroHDC), HistGradientBoosting (all DS1 beats).
Deterministic except the capped LDA's sample choice and boosting's internal seed; seeds 42..46 are run for the capped LDA and boosting.
Usage: python revision/aami_classic_baselines.py"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import aami_experiment as ae
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

half = 128
def feats(recs):
    X, y, g = [], [], []
    for rec in recs:
        sig = pd.read_csv(os.path.join(ae.DATA, f"{rec}.csv")).iloc[:, 1].values
        beats = [(s, ae.CLASS_OF[b]) for s, b in ae.parse(os.path.join(ae.DATA, f"{rec}annotations.txt")) if b in ae.CLASS_OF]
        sm = np.array([s for s, _ in beats], dtype=float)
        rr = np.diff(sm); rec_mean = float(np.mean(rr)) if len(rr) else 1.0
        for i, (s, c) in enumerate(beats):
            if c == "Q" or s < half or s > len(sig) - half: continue
            w = sig[s - half:s + half] - np.mean(sig[s - half:s + half]); pv = np.percentile(np.abs(w), 98)
            if pv > 0: w = np.clip(w, -pv, pv) / pv
            pre = sm[i] - sm[i - 1] if i > 0 else rec_mean
            post = sm[i + 1] - sm[i] if i + 1 < len(sm) else rec_mean
            lo = sm[max(0, i - 10):i + 1]; local = float(np.mean(np.diff(lo))) if len(lo) > 1 else rec_mean
            X.append(np.concatenate([w[::4], [pre, post, local, rec_mean, pre / rec_mean, post / rec_mean, pre / local]]))
            y.append(c); g.append(rec)
    return np.array(X, dtype=np.float64), np.array(y), np.array(g)
Xtr, ytr, _ = feats(ae.DS1); Xte, yte, _ = feats(ae.DS2)
print("train", len(ytr), {c: int((ytr == c).sum()) for c in ae.CLASSES}, "test", len(yte), {c: int((yte == c).sum()) for c in ae.CLASSES}, flush=True)
sc = StandardScaler().fit(Xtr); Xtr_s, Xte_s = sc.transform(Xtr), sc.transform(Xte)

def capped(sd):
    rng = np.random.RandomState(sd); sel = []
    for c in ae.CLASSES:
        idx = np.where(ytr == c)[0]; rng.shuffle(idx); sel += list(idx[: (12000 if c == "Normal" else 3000)])
    return np.array(sel)

def agg_runs(name, runs):
    a = {"model": name, "runs": runs}
    for key in ("accuracy", "macro_f1"):
        v = [r[key] for r in runs]; a[key] = f"{np.mean(v):.2f}+-{np.std(v):.2f}"
    for c in ae.CLASSES:
        for key in ("sensitivity", "ppv", "f1", "fpr"):
            v = [r["per_class"][c][key] for r in runs]; a[f"{c}_{key}"] = f"{np.nanmean(v):.2f}+-{np.nanstd(v):.2f}"
    return a

out = {}
m = ae.metrics(list(yte), list(LinearDiscriminantAnalysis().fit(Xtr_s, ytr).predict(Xte_s))); out["lda_all"] = agg_runs("LDA, all DS1 beats (De Chazal-style)", [m])
runs = []
for sd in ae.SEEDS:
    sel = capped(sd); runs.append(ae.metrics(list(yte), list(LinearDiscriminantAnalysis().fit(Xtr_s[sel], ytr[sel]).predict(Xte_s))))
out["lda_capped"] = agg_runs("LDA, 12000/3000 caps (same training subset size as NeuroHDC)", runs)
runs = []
for sd in ae.SEEDS:
    clf = HistGradientBoostingClassifier(random_state=sd, max_iter=200).fit(Xtr, ytr)
    runs.append(ae.metrics(list(yte), list(clf.predict(Xte))))
out["hgb_all"] = agg_runs("HistGradientBoosting, all DS1 beats", runs)
json.dump(out, open(os.path.join(os.path.dirname(__file__), "results", "aami_classic.json"), "w"), indent=1)
for k, a in out.items():
    print("==", k, a["model"], "acc", a["accuracy"], "macroF1", a["macro_f1"])
    for c in ae.CLASSES: print(f"   {c:7s} sens {a[c+'_sensitivity']:>13s} ppv {a[c+'_ppv']:>13s} fpr {a[c+'_fpr']:>13s}")
