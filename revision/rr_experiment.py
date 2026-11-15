"""Task 2: causal R-R feature + Pan-Tompkins sensitivity on MIT-BIH.

Identical protocol to scripts/01_train_python.py (rhythm binding):
  StratifiedGroupKFold(5, shuffle, seed 42), per-fold RandomState(42+fold), caps 12000/3000,
  one-shot prototypes + 30-epoch boundary refinement, same AssociativeMemory class,
  same bucket thresholds (0.85 / 1.15) and rhythm codebook (seed 42).
ONLY the R-R bucket assignment changes between variants (beat set, folds, morphology HVs fixed).

Variants
  off        no rhythm binding (morphology only)
  base       original: R-R from annotated peaks, whole-record median      (reproduces submitted setting)
  causal     annotated peaks, median of ALL strictly preceding R-R intervals in the record
  causal8    annotated peaks, median of the last <=8 strictly preceding R-R intervals
  pt_whole   Pan-Tompkins peaks, whole-record median (the submitted median, detected peaks)
  pt_causal  Pan-Tompkins peaks, causal expanding median
  pt_causal8 Pan-Tompkins peaks, trailing-8 causal median
Beats with no usable history / no matched detection fall back to NORMAL (as the original does for i==0).

Usage: python revision/rr_experiment.py <variant>
"""
import os, sys, json, time
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
from src.config import SHDEConfig
from src.associative_mem import AssociativeMemory
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score
import pan_tompkins as pt

BASE_SEED, MAX_NORMAL, MAX_ANOMALY, EPOCHS = 42, 12000, 3000, 30
SHORT, LONG = 0.85, 1.15
BUCKETS = ["SHORT", "NORMAL", "LONG"]


def bipolar(v):
    return np.where(np.asarray(v) > 0, 1, -1).astype(np.int32)


def bucket(rr, med):
    if med is None or med <= 0:
        return "NORMAL"
    r = rr / med
    return "SHORT" if r < SHORT else "LONG" if r > LONG else "NORMAL"


def median_ref(rr, i, mode):
    """Reference interval for beat i given interval list rr (rr[k] = peak[k]-peak[k-1], rr[0] unused/0)."""
    if mode == "whole":
        pos = rr[rr > 0]
        return float(np.median(pos)) if len(pos) else None
    hist = rr[1:i]  # intervals strictly preceding beat i's own interval rr[i]
    hist = hist[hist > 0]
    if mode == "causal8":
        hist = hist[-8:]
    return float(np.median(hist)) if len(hist) else None


def buckets_for(peaks_by_rec, mode, y_groups):
    """Returns per-beat bucket array in cache order. peaks_by_rec: rec -> (seq of R positions used for RR, per-beat index or -1)."""
    out = np.empty(len(y_groups), dtype=object)
    pos = {}
    for rec, (seq, bidx) in peaks_by_rec.items():
        seq = np.asarray(seq)
        rr = np.diff(seq, prepend=seq[0]) if len(seq) else seq
        idxs = np.nonzero(y_groups == rec)[0]
        pos[rec] = idxs
        whole = median_ref(rr, 0, "whole") if (mode == "whole" and len(seq)) else None
        for n, gi in enumerate(idxs):
            j = bidx[n]
            if j <= 0:  # no detection matched, or first peak -> no interval
                out[gi] = "NORMAL"
                continue
            med = whole if mode == "whole" else median_ref(rr, j, mode)
            out[gi] = bucket(rr[j], med)
    return out


def variant_buckets(variant, cache, data_dir):
    groups, peaks = cache["groups"], cache["peaks"]
    recs = list(dict.fromkeys(groups))
    mode = {"base": "whole", "causal": "causal", "causal8": "causal8",
            "pt_whole": "whole", "pt_causal": "causal", "pt_causal8": "causal8"}[variant]
    by_rec = {}
    if variant.startswith("pt_"):
        det = np.load(os.path.join(ROOT, "revision", "cache", "pt_peaks.npz"))
        for rec in recs:
            d = det[f"rec_{rec}"]
            used = peaks[groups == rec]
            by_rec[rec] = (d, pt.match(used, d))
    else:
        for rec in recs:
            used = peaks[groups == rec]
            by_rec[rec] = (used, np.arange(len(used)))
    return buckets_for(by_rec, mode, groups)


def main():
    variant = sys.argv[1]
    data_dir = sys.argv[2] if len(sys.argv) > 2 else None
    t0 = time.time()
    cache = np.load(os.path.join(ROOT, "revision", "cache", "mitbih_cache.npz"), allow_pickle=True)
    D = int(cache["D"])
    hv = np.unpackbits(cache["hv"], axis=1)[:, :D].astype(np.int8)
    y, groups = cache["y"], cache["groups"]
    rhythm = variant != "off"
    rr = variant_buckets(variant, cache, data_dir) if rhythm else np.array([None] * len(y), dtype=object)

    if rhythm:
        vals, cnt = np.unique(rr, return_counts=True)
        dist = {k: round(100 * c / len(rr), 2) for k, c in zip(vals, cnt)}
    else:
        dist = {}
    print(f"[{variant}] beats={len(y)} bucket% = {dist}", flush=True)

    rng_cb = np.random.RandomState(BASE_SEED)
    codebook = {b: bipolar(rng_cb.choice([-1, 1], size=D)) for b in BUCKETS}

    def bind(h, b):
        return np.where(bipolar(h) * codebook[b] > 0, 1, 0).astype(np.int8)

    cfg = SHDEConfig()
    kf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=BASE_SEED)
    X_dummy = np.zeros(len(y))
    res = {"variant": variant, "bucket_pct": dist, "folds": []}
    allt, allp = [], []
    for fold, (tr, te) in enumerate(kf.split(X_dummy, y, groups=groups)):
        assert not (set(groups[tr]) & set(groups[te]))
        rng = np.random.RandomState(BASE_SEED + fold)
        memory = AssociativeMemory(cfg)
        ytr = y[tr]
        train = []
        for label in np.unique(ytr):  # same iteration/shuffle order as the original
            li = np.where(ytr == label)[0]
            rng.shuffle(li)
            cap = MAX_NORMAL if label == "Normal" else MAX_ANOMALY
            for k in li[:cap]:
                train.append((tr[k], label))
        rng.shuffle(train)

        train_hvs = []
        for gi, label in train:
            h = hv[gi]
            if rhythm:
                h = bind(h, rr[gi] if rr[gi] is not None else "NORMAL")
            memory.add_to_class(h, label)
            train_hvs.append((h, label))
        memory.finalize_prototypes()
        for label in memory.prototype_sums:
            memory.prototype_sums[label] = 2 * memory.prototype_sums[label] - memory.prototype_counts[label]
        for epoch in range(EPOCHS):
            mistakes = 0
            rng.shuffle(train_hvs)
            LR = max(1, int(15 * (1.0 - (epoch / EPOCHS))))
            for h, tl in train_hvs:
                pl, _ = memory.predict(h)
                if pl != tl:
                    mistakes += 1
                    b = bipolar(h)
                    memory.prototype_sums[pl] -= b * LR
                    memory.prototype_sums[tl] += b * LR
            for label in memory.prototype_sums:
                memory.prototypes[label] = (memory.prototype_sums[label] > 0).astype(np.int8)
            if mistakes == 0:
                break

        yt, yp = [], []
        for gi in te:
            h = hv[gi]
            if rhythm:
                h = bind(h, rr[gi] if rr[gi] is not None else "NORMAL")
            pl, _ = memory.predict(h)
            yt.append(y[gi]); yp.append(pl)
        acc = 100 * np.mean(np.array(yt) == np.array(yp))
        labels = list(set(yt) | set(yp))
        f1 = 100 * f1_score(yt, yp, labels=labels, average="macro")
        per_cls = dict(zip(sorted(labels), (100 * f1_score(yt, yp, labels=sorted(labels), average=None)).round(2).tolist()))
        res["folds"].append({"fold": fold + 1, "acc": acc, "macro_f1": f1, "per_class_f1": per_cls,
                             "n_test": len(te), "refine_epochs_run": epoch + 1})
        allt += yt; allp += yp
        print(f"[{variant}] fold {fold+1}: acc {acc:.2f}  macroF1 {f1:.2f}  ({time.time()-t0:.0f}s)", flush=True)

    accs = [f["acc"] for f in res["folds"]]; f1s = [f["macro_f1"] for f in res["folds"]]
    res["acc_mean"], res["acc_std"] = float(np.mean(accs)), float(np.std(accs))
    res["f1_mean"], res["f1_std"] = float(np.mean(f1s)), float(np.std(f1s))
    labs = sorted(set(allt))
    res["pooled_per_class_f1"] = dict(zip(labs, (100 * f1_score(allt, allp, labels=labs, average=None)).round(2).tolist()))
    print(f"[{variant}] FINAL acc {res['acc_mean']:.2f}±{res['acc_std']:.2f}  macroF1 {res['f1_mean']:.2f}±{res['f1_std']:.2f}")
    print(f"[{variant}] pooled per-class F1: {res['pooled_per_class_f1']}")
    with open(os.path.join(ROOT, "revision", "results", f"rr_{variant}.json"), "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
