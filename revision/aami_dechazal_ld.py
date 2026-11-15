"""De Chazal et al. 2004 (IEEE TBME 51(7):1196-1206) fixed-interval configurations, re-implemented from the paper text (revision prep only).

Reproduced (paper Sections IV-D..F, G): single-lead configurations III/VII (feature sets FS3 = lead A, FS7 = lead B: 4 R-R features +
18 fixed-interval morphology features, unscaled) and the multi-lead configuration XI (FS3 + FS7, two linear-discriminant classifiers
combined by the product of posteriors). NOT reproduced: his selected configuration IX (FS1+FS5) because it needs the Laguna `ecgpuwave`
QRS/T-wave segmentation program (QRS onset/offset, T-wave offset, P-wave presence), which is not available here.

Details taken from the paper:  filtering = 200 ms then 600 ms median filters (baseline), subtracted, then a 12-tap equiripple FIR low-pass
with 3 dB point at 35 Hz (designed here with scipy.signal.remez; applied zero-phase with filtfilt, an assumption); fiducial = annotated beat;
R-R features: pre-RR, post-RR, recording-average RR, local average of the ten RR intervals surrounding the beat (5 before, 5 after);
morphology: 10 samples FP-50..+100 ms at 60 Hz and 8 samples FP+150..+500 ms at 20 Hz per lead; classifier = linear discriminants with
"plug-in" ML estimates, per-class training weights so each class contributes about 400 examples (w = 400/n if n > 400 else 1), equal
priors for N,S,V,F (paper: 10/41 each; Q 1/41 and Q is dropped here), posterior-product combination.
Differences from the paper: Q beats dropped (4-class, as requested); AAMI measures computed on 4 classes; the filter design is approximate.

Validation targets quoted in the paper text for DS1 record-wise 22-fold cross-validation (5-class incl. Q): configuration VII accuracy 83.0%,
sensitivities SVEB 30.4 / VEB 39.9 / F 32.1; configuration XI accuracy 86.2%, SVEB 54.7 / VEB 40.0 / F 26.0. These are used to check this
re-implementation. DS1/DS2 as in aami_experiment.py. Usage: python revision/aami_dechazal_ld.py"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.ndimage import median_filter
from scipy.signal import remez, filtfilt
sys.path.insert(0, os.path.dirname(__file__))
import aami_experiment as ae

FS = 360
LP = remez(12, [0, 30, 40, FS / 2], [1, 0], fs=FS)
QRS_OFF = np.arange(-18, 37, 6)            # FP-50 ms .. FP+100 ms at 60 Hz -> 10 samples
T_OFF = np.arange(54, 181, 18)             # FP+150 ms .. FP+500 ms at 20 Hz -> 8 samples
assert len(QRS_OFF) == 10 and len(T_OFF) == 8


def prep(x):
    base = median_filter(median_filter(x.astype(float), size=73, mode="nearest"), size=217, mode="nearest")   # 200 ms then 600 ms
    return filtfilt(LP, [1.0], x - base)


def record_features(rec):
    df = pd.read_csv(os.path.join(ae.DATA, f"{rec}.csv"))
    leadA, leadB = prep(df.iloc[:, 1].values), prep(df.iloc[:, 2].values)
    beats = [(s, ae.CLASS_OF[b]) for s, b in ae.parse(os.path.join(ae.DATA, f"{rec}annotations.txt")) if b in ae.CLASS_OF]
    sm = np.array([s for s, _ in beats], dtype=float); rr = np.diff(sm); rec_mean = float(np.mean(rr))
    rows = {"A": [], "B": []}; y = []; idx = []
    for i, (s, c) in enumerate(beats):
        if c == "Q" or s + T_OFF[-1] >= len(leadA) or s + QRS_OFF[0] < 0: continue
        pre = sm[i] - sm[i - 1] if i > 0 else rec_mean
        post = sm[i + 1] - sm[i] if i + 1 < len(sm) else rec_mean
        lo, hi = max(0, i - 5), min(len(sm) - 1, i + 5)
        local = float(np.mean(np.diff(sm[lo:hi + 1]))) if hi > lo else rec_mean
        rrf = [pre, post, rec_mean, local]
        for name, sig in (("A", leadA), ("B", leadB)):
            rows[name].append(np.concatenate([rrf, sig[s + QRS_OFF], sig[s + T_OFF]]))
        y.append(c)
    return np.array(rows["A"]), np.array(rows["B"]), np.array(y)


class WLD:
    """Weighted linear discriminant (paper eqs. 1-5): class means, common covariance, class-dependent example weights."""
    def fit(self, X, y, classes, target=400):
        self.classes = classes; self.mu = {}; num = np.zeros((X.shape[1],) * 2); den = 0.0
        for c in classes:
            Xc = X[y == c]; n = len(Xc); w = target / n if n > target else 1.0
            self.mu[c] = Xc.mean(0); d = Xc - self.mu[c]; num += w * d.T @ d; den += w * n
        self.P = np.linalg.pinv(num / den); self.logp = np.log(1.0 / len(classes))     # equal priors (10/41 each in the paper)
        return self
    def posterior(self, X):
        d = np.stack([X @ self.P @ self.mu[c] - 0.5 * self.mu[c] @ self.P @ self.mu[c] + self.logp for c in self.classes], 1)
        d -= d.max(1, keepdims=True); p = np.exp(d); return p / p.sum(1, keepdims=True)


def fit_predict(trA, trB, ytr, teA, teB, cfg):
    cls = ae.CLASSES; posts = []
    for use, tr, te in (("A", trA, teA), ("B", trB, teB)):
        if use not in cfg: continue
        mu, sd = tr.mean(0), tr.std(0) + 1e-9
        posts.append(WLD().fit((tr - mu) / sd, ytr, cls).posterior((te - mu) / sd))
    p = np.prod(posts, axis=0)                               # unweighted product of posteriors (paper eq. 6)
    return np.array(cls)[p.argmax(1)]


def aami(yt, yp):
    """AAMI measures per the paper's Table V: VEB FP excludes F->V; SVEB FP: all non-S beats called S (no Q here)."""
    yt, yp = np.array(yt), np.array(yp); out = {}
    tp = ((yt == "VEB") & (yp == "VEB")).sum(); fn = ((yt == "VEB") & (yp != "VEB")).sum()
    fp = (((yt == "Normal") | (yt == "SVEB")) & (yp == "VEB")).sum(); tn = (((yt == "Normal") | (yt == "SVEB")) & (yp != "VEB")).sum()
    out["VEB"] = dict(sens=100 * tp / (tp + fn), ppv=100 * tp / (tp + fp), fpr=100 * fp / (fp + tn))
    tp = ((yt == "SVEB") & (yp == "SVEB")).sum(); fn = ((yt == "SVEB") & (yp != "SVEB")).sum()
    fp = ((yt != "SVEB") & (yp == "SVEB")).sum(); tn = ((yt != "SVEB") & (yp != "SVEB")).sum()
    out["SVEB"] = dict(sens=100 * tp / (tp + fn), ppv=100 * tp / (tp + fp), fpr=100 * fp / (fp + tn))
    return out


def main():
    data = {}
    for rec in ae.DS1 + ae.DS2:
        data[rec] = record_features(rec); print(rec, len(data[rec][2]), flush=True)
    def stack(recs):
        return (np.vstack([data[r][0] for r in recs]), np.vstack([data[r][1] for r in recs]), np.concatenate([data[r][2] for r in recs]),
                np.concatenate([[r] * len(data[r][2]) for r in recs]))
    A1, B1, y1, g1 = stack(ae.DS1); A2, B2, y2, g2 = stack(ae.DS2)
    print("DS1", {c: int((y1 == c).sum()) for c in ae.CLASSES}, "DS2", {c: int((y2 == c).sum()) for c in ae.CLASSES})
    res = {}
    for name, cfg in (("III (FS3, lead A)", "A"), ("VII (FS7, lead B)", "B"), ("XI (FS3+FS7, two leads)", "AB")):
        # DD1: leave-one-record-out cross-validation on DS1 (22 folds), aggregated gross statistics
        yp = np.empty(len(y1), dtype=object)
        for r in ae.DS1:
            te = g1 == r; yp[te] = fit_predict(A1[~te], B1[~te], y1[~te], A1[te], B1[te], cfg)
        cv = ae.metrics(list(y1), list(yp))
        # final: train on DS1, test on DS2
        yq = fit_predict(A1, B1, y1, A2, B2, cfg); te_m = ae.metrics(list(y2), list(yq))
        res[name] = dict(ds1_cv=cv, ds2=te_m, ds2_aami=aami(y2, yq), ds1_cv_aami=aami(y1, yp))
        pc = cv["per_class"]
        print(f"== {name}\n  DS1 record-wise CV: acc {cv['accuracy']:.1f}  sens " + " ".join(f"{c} {pc[c]['sensitivity']:.1f}" for c in ae.CLASSES))
        pt = te_m["per_class"]
        print(f"  DS2: acc {te_m['accuracy']:.1f} macroF1 {te_m['macro_f1']:.1f} sens " + " ".join(f"{c} {pt[c]['sensitivity']:.1f}" for c in ae.CLASSES))
        print("  DS2 AAMI:", {k: {m: round(v, 1) for m, v in d.items()} for k, d in res[name]["ds2_aami"].items()}, flush=True)
    json.dump(res, open(os.path.join(os.path.dirname(__file__), "results", "aami_dechazal_ld.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
