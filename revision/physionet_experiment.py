"""PhysioNet 2017: rhythm variants (off / whole-record median [submitted] / causal / causal8), paper protocol
(StratifiedGroupKFold 5, seed 42, caps 12000/3000, 30-epoch refinement; macro-F1 excludes 'Noisy')."""
import os, sys, json, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from src.config import SHDEConfig
from src.associative_mem import AssociativeMemory
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score
variant = sys.argv[1]
c = np.load(os.path.join(ROOT, "revision/cache/physionet_cache.npz"), allow_pickle=True)
D = 4096; hv = np.unpackbits(c["hv"], axis=1)[:, :D].astype(np.int8); y, g = c["y"], c["g"]
med = {"whole": c["mw"], "causal": c["mc"], "causal8": c["mc8"]}.get(variant)
cfg = SHDEConfig(); SEED = 42
bip = lambda v: np.where(np.asarray(v) > 0, 1, -1).astype(np.int32)
rng_cb = np.random.RandomState(SEED); cb = {b: bip(rng_cb.choice([-1, 1], size=D)) for b in ["SHORT", "NORMAL", "LONG"]}
if med is None: bk = None
else:
    r = c["rr"] / med; bk = np.full(len(y), "NORMAL", dtype=object); ok = ~np.isnan(r)
    bk[ok & (r < 0.85)] = "SHORT"; bk[ok & (r > 1.15)] = "LONG"
    print(variant, "bucket %:", {k: round(100 * float((bk == k).mean()), 2) for k in ["SHORT", "NORMAL", "LONG"]}, flush=True)
def enc(i):
    h = hv[i]
    return h if bk is None else np.where(bip(h) * cb[bk[i]] > 0, 1, 0).astype(np.int8)
kf = StratifiedGroupKFold(5, shuffle=True, random_state=SEED); accs, f1s = [], []
for fold, (tr, te) in enumerate(kf.split(np.zeros(len(y)), y, groups=g)):
    rng = np.random.RandomState(SEED + fold); mem = AssociativeMemory(cfg); ytr = y[tr]; train = []
    for lab in np.unique(ytr):
        li = np.where(ytr == lab)[0]; rng.shuffle(li)
        for k in li[: (12000 if lab == "Normal" else 3000)]: train.append((tr[k], lab))
    rng.shuffle(train); th = []
    for gi, lab in train: h = enc(gi); mem.add_to_class(h, lab); th.append((h, lab))
    mem.finalize_prototypes()
    for lab in mem.prototype_sums: mem.prototype_sums[lab] = 2 * mem.prototype_sums[lab] - mem.prototype_counts[lab]
    for ep in range(30):
        mist = 0; rng.shuffle(th); LR = max(1, int(15 * (1 - ep / 30)))
        for h, tl in th:
            pl, _ = mem.predict(h)
            if pl != tl: mist += 1; b = bip(h); mem.prototype_sums[pl] -= b * LR; mem.prototype_sums[tl] += b * LR
        for lab in mem.prototype_sums: mem.prototypes[lab] = (mem.prototype_sums[lab] > 0).astype(np.int8)
        if mist == 0: break
    yt = list(y[te]); yp = [mem.predict(enc(i))[0] for i in te]
    labs = set(yt) | set(yp); labs.discard("Noisy")
    accs.append(100 * np.mean(np.array(yt) == np.array(yp))); f1s.append(100 * f1_score(yt, yp, labels=list(labs), average="macro"))
    print(variant, "fold", fold + 1, round(accs[-1], 2), round(f1s[-1], 2), flush=True)
res = dict(variant=variant, acc=f"{np.mean(accs):.2f}±{np.std(accs):.2f}", f1=f"{np.mean(f1s):.2f}±{np.std(f1s):.2f}", fold_f1=[round(v, 2) for v in f1s], fold_acc=[round(v, 2) for v in accs])
print("FINAL", res); json.dump(res, open(os.path.join(ROOT, f"revision/results/physionet_{variant}.json"), "w"), indent=1)
