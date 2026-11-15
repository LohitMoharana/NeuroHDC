"""Task 3: nested-validation accuracy experiments on MIT-BIH (revision preparation only).

For ONE change family and ONE outer fold (same StratifiedGroupKFold(5, shuffle, seed 42) as the paper):
  1. inside the outer TRAIN records only, run a 3-fold StratifiedGroupKFold (seed 42, grouped by record);
  2. score every candidate setting of the family by mean inner-validation macro-F1
     (candidate 0 is always the submitted setting; ties keep the earliest candidate);
  3. refit the winner on the full outer-train with the paper's RandomState(42+fold) and score it ONCE on the
     untouched outer test fold.
The outer test fold never influences the choice. Everything not in the family stays at the submitted setting
(annotated R peaks, whole-record median, caps 12000/3000, LR 15 / 30 epochs, thresholds 0.05/0.25/0.6,
buckets 0.85/1.15). If candidate 0 wins, the result equals the submitted fold result (self-check).

Usage: python revision/nested_experiment.py <family> <outer_fold 0-4>
families: schedule | caps | rhythm | tokenizer
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
import rr_experiment as rx

SEED = 42
BASE = dict(lr0=15, epochs=30, cap_n=12000, cap_a=3000, short=0.85, long=1.15, tok="base")
FAMILIES = {
    "schedule": [dict(), dict(lr0=5), dict(lr0=30), dict(epochs=10), dict(epochs=60), dict(epochs=0)],
    "caps": [dict(), dict(cap_n=3000), dict(cap_n=6000, cap_a=6000), dict(cap_a=6000),
             dict(cap_n=12000, cap_a=12000), dict(cap_n=1500)],
    "rhythm": [dict(), dict(short=0.9, long=1.1), dict(short=0.8, long=1.2),
               dict(short=0.75, long=1.25), dict(short=0.9, long=1.2)],
    "tokenizer": [dict(), dict(tok="t_lo"), dict(tok="t_hi"), dict(tok="t_mid"), dict(tok="t_wide")],
}
TOK_THRESH = {"base": [0.05, 0.25, 0.6], "t_lo": [0.03, 0.15, 0.4], "t_hi": [0.08, 0.3, 0.7],
              "t_mid": [0.05, 0.15, 0.4], "t_wide": [0.1, 0.25, 0.5]}


class Data:
    def __init__(self):
        c = np.load(os.path.join(ROOT, "revision", "cache", "mitbih_cache.npz"), allow_pickle=True)
        self.y, self.groups, self.peaks, self.D = c["y"], c["groups"], c["peaks"], int(c["D"])
        self.packed = {"base": c["hv"]}
        # per-beat R-R ratio (rr / whole-record median of annotated peaks); NaN = no rhythm info -> NORMAL
        self.ratio = np.full(len(self.y), np.nan)
        for rec in dict.fromkeys(self.groups):
            idx = np.nonzero(self.groups == rec)[0]
            seq = self.peaks[idx]
            rr = np.diff(seq, prepend=seq[0])
            med = rx.median_ref(rr, 0, "whole")
            if med and med > 0:
                self.ratio[idx[1:]] = rr[1:] / med
        self.rng_cb = np.random.RandomState(SEED)
        self.codebook = {b: rx.bipolar(self.rng_cb.choice([-1, 1], size=self.D)) for b in rx.BUCKETS}

    def hv(self, tok, idx):
        if tok not in self.packed:
            self.packed[tok] = np.load(os.path.join(ROOT, "revision", "cache", f"tok_{tok}.npz"))["hv"]
        return np.unpackbits(self.packed[tok][idx], axis=1)[:, :self.D].astype(np.int8)

    def buckets(self, idx, short, long):
        r = self.ratio[idx]
        out = np.full(len(idx), "NORMAL", dtype=object)
        ok = ~np.isnan(r)
        out[ok & (r < short)] = "SHORT"
        out[ok & (r > long)] = "LONG"
        return out


def bind(D, h, b):
    return np.where(rx.bipolar(h) * D.codebook[b] > 0, 1, 0).astype(np.int8)


def fit_predict(D, tr, te, p, seed):
    """Paper's training loop (scripts/01_train_python.py) with parameters p; returns (y_true, y_pred) on te."""
    cfg = SHDEConfig()
    rng = np.random.RandomState(seed)
    memory = AssociativeMemory(cfg)
    ytr = D.y[tr]
    train = []
    for label in np.unique(ytr):
        li = np.where(ytr == label)[0]
        rng.shuffle(li)
        cap = p["cap_n"] if label == "Normal" else p["cap_a"]
        for k in li[:cap]:
            train.append(tr[k])
    train = np.array(train)
    order = np.arange(len(train))
    # original shuffles a list of (wave,label,rr) tuples; permutation depends only on length -> same stream
    rng.shuffle(order)
    train = train[order]
    hv_tr = D.hv(p["tok"], train)
    bk_tr = D.buckets(train, p["short"], p["long"])
    train_hvs = []
    for h, b, gi in zip(hv_tr, bk_tr, train):
        h = bind(D, h, b)
        memory.add_to_class(h, D.y[gi])
        train_hvs.append((h, D.y[gi]))
    memory.finalize_prototypes()
    for label in memory.prototype_sums:
        memory.prototype_sums[label] = 2 * memory.prototype_sums[label] - memory.prototype_counts[label]
    for epoch in range(p["epochs"]):
        mistakes = 0
        rng.shuffle(train_hvs)
        LR = max(1, int(p["lr0"] * (1.0 - (epoch / p["epochs"]))))
        for h, tl in train_hvs:
            pl, _ = memory.predict(h)
            if pl != tl:
                mistakes += 1
                bp = rx.bipolar(h)
                memory.prototype_sums[pl] -= bp * LR
                memory.prototype_sums[tl] += bp * LR
        for label in memory.prototype_sums:
            memory.prototypes[label] = (memory.prototype_sums[label] > 0).astype(np.int8)
        if mistakes == 0:
            break
    hv_te = D.hv(p["tok"], te)
    bk_te = D.buckets(te, p["short"], p["long"])
    yp = [memory.predict(bind(D, h, b))[0] for h, b in zip(hv_te, bk_te)]
    return list(D.y[te]), yp


def macro_f1(yt, yp):
    return 100 * f1_score(yt, yp, labels=list(set(yt) | set(yp)), average="macro")


def main():
    family, fold = sys.argv[1], int(sys.argv[2])
    t0 = time.time()
    D = Data()
    kf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    tr, te = list(kf.split(np.zeros(len(D.y)), D.y, groups=D.groups))[fold]
    assert not (set(D.groups[tr]) & set(D.groups[te]))
    cands = [{**BASE, **c} for c in FAMILIES[family]]

    inner = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=SEED)
    isplits = list(inner.split(np.zeros(len(tr)), D.y[tr], groups=D.groups[tr]))
    scores = []
    for ci, p in enumerate(cands):
        fs = []
        for k, (itr, iva) in enumerate(isplits):
            yt, yp = fit_predict(D, tr[itr], tr[iva], p, SEED + 100 * fold + k)
            fs.append(macro_f1(yt, yp))
        scores.append(float(np.mean(fs)))
        print(f"[{family} f{fold}] cand {ci} {FAMILIES[family][ci]} inner macroF1 {scores[-1]:.2f} "
              f"(folds {[round(v,2) for v in fs]}) {time.time()-t0:.0f}s", flush=True)
    best = int(np.argmax(scores))  # first max wins -> submitted setting on ties
    yt, yp = fit_predict(D, tr, te, cands[best], SEED + fold)
    acc = 100 * float(np.mean(np.array(yt) == np.array(yp)))
    f1 = macro_f1(yt, yp)
    res = dict(family=family, outer_fold=fold + 1, candidates=FAMILIES[family], inner_scores=scores,
               selected=best, selected_setting=FAMILIES[family][best], outer_acc=acc, outer_macro_f1=f1,
               inner_train_records=len(set(D.groups[tr])), n_test=len(te))
    print(f"[{family} f{fold}] SELECTED cand {best} {FAMILIES[family][best]} -> outer acc {acc:.2f} macroF1 {f1:.2f}")
    with open(os.path.join(ROOT, "revision", "results", f"nested_{family}_f{fold+1}.json"), "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
