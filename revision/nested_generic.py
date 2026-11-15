"""Nested validation on PTB or ST-T (no rhythm in the submitted pipeline) -- derived from nested_physionet.py.
Nested validation on PhysioNet 2017 (revision preparation only; the submitted five-fold numbers stay final).

Same design as nested_experiment.py (MIT-BIH): outer StratifiedGroupKFold(5, shuffle, seed 42) by record; inside each
outer TRAIN set a 3-fold StratifiedGroupKFold (seed 42, by record) scores every candidate of ONE family by mean inner
macro-F1; candidate 0 is the submitted setting and wins ties; the winner is refit on the full outer-train with
RandomState(42+fold) and scored once on the untouched outer test fold. Macro-F1 excludes 'Noisy' (as submitted).
Rhythm = whole-record median (as submitted, cache column `mw`). Tokenizer family is not run (the cache holds only
the submitted-threshold hypervectors).

Usage: python revision/nested_generic.py <ptb|stt> <schedule|caps> <outer_fold 0-4>
"""
import os, sys, json, time
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from src.config import SHDEConfig
from src.associative_mem import AssociativeMemory
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score

SEED = 42
BASE = dict(lr0=15, epochs=30, cap_n=12000, cap_a=3000, rhythm=False)
FAMILIES = {
    "schedule": [dict(), dict(lr0=5), dict(lr0=30), dict(epochs=10), dict(epochs=60), dict(epochs=0)],
    "caps": [dict(), dict(cap_n=3000), dict(cap_n=6000, cap_a=6000), dict(cap_a=6000),
             dict(cap_n=12000, cap_a=12000), dict(cap_n=1500)],
}
bip = lambda v: np.where(np.asarray(v) > 0, 1, -1).astype(np.int32)


class Data:
    def __init__(self, name):
        c = np.load(os.path.join(ROOT, "revision", "cache", f"{name}_cache.npz"), allow_pickle=True)
        self.D = 4096
        self.hv = np.unpackbits(c["hv"], axis=1)[:, :self.D].astype(np.int8)
        self.y, self.g = c["y"], c["g"]

    def enc(self, idx, p):
        return self.hv[idx]


def fit_predict(D, tr, te, p, seed):
    cfg = SHDEConfig()
    rng = np.random.RandomState(seed)
    mem = AssociativeMemory(cfg)
    ytr = D.y[tr]
    train = []
    for lab in np.unique(ytr):
        li = np.where(ytr == lab)[0]
        rng.shuffle(li)
        cap = p["cap_n"] if lab == "Normal" else p["cap_a"]
        for k in li[:cap]:
            train.append(tr[k])
    train = np.array(train)
    order = np.arange(len(train))
    rng.shuffle(order)
    train = train[order]
    H = D.enc(train, p)
    th = []
    for h, gi in zip(H, train):
        mem.add_to_class(h, D.y[gi])
        th.append((h, D.y[gi]))
    mem.finalize_prototypes()
    for lab in mem.prototype_sums:
        mem.prototype_sums[lab] = 2 * mem.prototype_sums[lab] - mem.prototype_counts[lab]
    for ep in range(p["epochs"]):
        mist = 0
        rng.shuffle(th)
        LR = max(1, int(p["lr0"] * (1.0 - ep / p["epochs"])))
        for h, tl in th:
            pl, _ = mem.predict(h)
            if pl != tl:
                mist += 1
                b = bip(h)
                mem.prototype_sums[pl] -= b * LR
                mem.prototype_sums[tl] += b * LR
        for lab in mem.prototype_sums:
            mem.prototypes[lab] = (mem.prototype_sums[lab] > 0).astype(np.int8)
        if mist == 0:
            break
    Hte = D.enc(te, p)
    yp = [mem.predict(h)[0] for h in Hte]
    return list(D.y[te]), yp


def macro_f1(yt, yp):
    labs = set(yt) | set(yp)
    return 100 * f1_score(yt, yp, labels=list(labs), average="macro")


def main():
    ds, family, fold = sys.argv[1], sys.argv[2], int(sys.argv[3])
    t0 = time.time()
    D = Data(ds)
    kf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    tr, te = list(kf.split(np.zeros(len(D.y)), D.y, groups=D.g))[fold]
    assert not (set(D.g[tr]) & set(D.g[te]))
    cands = [{**BASE, **c} for c in FAMILIES[family]]
    inner = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=SEED)
    isplits = list(inner.split(np.zeros(len(tr)), D.y[tr], groups=D.g[tr]))
    scores = []
    for ci, p in enumerate(cands):
        fs = []
        for k, (itr, iva) in enumerate(isplits):
            yt, yp = fit_predict(D, tr[itr], tr[iva], p, SEED + 100 * fold + k)
            fs.append(macro_f1(yt, yp))
        scores.append(float(np.mean(fs)))
        print(f"[{ds} {family} f{fold}] cand {ci} {FAMILIES[family][ci]} inner macroF1 {scores[-1]:.2f} "
              f"{time.time()-t0:.0f}s", flush=True)
    best = int(np.argmax(scores))
    yt, yp = fit_predict(D, tr, te, cands[best], SEED + fold)
    acc = 100 * float(np.mean(np.array(yt) == np.array(yp)))
    f1 = macro_f1(yt, yp)
    res = dict(dataset=ds, family=family, outer_fold=fold + 1, candidates=FAMILIES[family],
               inner_scores=scores, selected=best, selected_setting=FAMILIES[family][best],
               outer_acc=acc, outer_macro_f1=f1, n_test=len(te))
    print(f"[{ds} {family} f{fold}] SELECTED cand {best} {FAMILIES[family][best]} -> outer acc {acc:.2f} macroF1 {f1:.2f}")
    with open(os.path.join(ROOT, "revision", "results", f"nested_{ds}_{family}_f{fold+1}.json"), "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
