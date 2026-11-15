"""Weakness 7: PTB grouped by file name vs by patient (PhysioNet RECORDS list). Same loader, encoder, caps,
refinement loop, StratifiedGroupKFold(5, shuffle, seed 42) as scripts/01_train_python.py (no rhythm)."""
import os, sys, json, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from src.config import SHDEConfig
from src.tokenizer import DeltaTokenizer
from src.hdc_encoding import HDCEncoder
from src.associative_mem import AssociativeMemory
from src.data_loader import PTBLoader
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score

DATA = sys.argv[1]
SEED, MAXN, MAXA, EPOCHS = 42, 12000, 3000, 30
cfg = SHDEConfig(); tok = DeltaTokenizer(thresholds=[0.05, 0.25, 0.6]); enc = HDCEncoder(cfg)
X, y, g = PTBLoader(DATA).load_dataset()
y, g = np.array(y), np.array(g)
rec2pat = {l.strip().split('/')[1]: l.strip().split('/')[0] for l in open(os.path.join(ROOT, "revision/data_external/ptbdb_RECORDS.txt")) if l.strip()}
def rec_of(name): return os.path.splitext(str(name))[0]
pat = np.array([rec2pat[rec_of(n)] for n in g])
print("beats", len(y), "classes", {k: int((y == k).sum()) for k in np.unique(y)}, "file-groups", len(set(g)), "patient-groups", len(set(pat)))
hv = np.array([enc.encode_sequence(tok.encode(w)) for w in X], dtype=np.int8)
bip = lambda v: np.where(np.asarray(v) > 0, 1, -1).astype(np.int32)

def run(groups, name):
    kf = StratifiedGroupKFold(5, shuffle=True, random_state=SEED)
    accs, f1s, leak = [], [], []
    for fold, (tr, te) in enumerate(kf.split(np.zeros(len(y)), y, groups=groups)):
        assert not (set(groups[tr]) & set(groups[te]))
        leak.append(len(set(pat[tr]) & set(pat[te])))      # patients appearing in both train and test
        rng = np.random.RandomState(SEED + fold); mem = AssociativeMemory(cfg); ytr = y[tr]; train = []
        for lab in np.unique(ytr):
            li = np.where(ytr == lab)[0]; rng.shuffle(li)
            for k in li[: (MAXN if lab == "Normal" else MAXA)]: train.append((tr[k], lab))
        rng.shuffle(train)
        th = []
        for gi, lab in train: mem.add_to_class(hv[gi], lab); th.append((hv[gi], lab))
        mem.finalize_prototypes()
        for lab in mem.prototype_sums: mem.prototype_sums[lab] = 2 * mem.prototype_sums[lab] - mem.prototype_counts[lab]
        for ep in range(EPOCHS):
            mist = 0; rng.shuffle(th); LR = max(1, int(15 * (1 - ep / EPOCHS)))
            for h, tl in th:
                pl, _ = mem.predict(h)
                if pl != tl: mist += 1; b = bip(h); mem.prototype_sums[pl] -= b * LR; mem.prototype_sums[tl] += b * LR
            for lab in mem.prototype_sums: mem.prototype_sums[lab] = mem.prototype_sums[lab]; mem.prototypes[lab] = (mem.prototype_sums[lab] > 0).astype(np.int8)
            if mist == 0: break
        yt = list(y[te]); yp = [mem.predict(hv[i])[0] for i in te]
        accs.append(100 * np.mean(np.array(yt) == np.array(yp)))
        f1s.append(100 * f1_score(yt, yp, labels=list(set(yt) | set(yp)), average="macro"))
    r = dict(grouping=name, acc=f"{np.mean(accs):.2f}±{np.std(accs):.2f}", f1=f"{np.mean(f1s):.2f}±{np.std(f1s):.2f}",
             fold_f1=[round(v, 2) for v in f1s], patients_in_both_train_and_test_per_fold=leak)
    print(r, flush=True); return r
res = [run(g, "file name (as submitted)"), run(pat, "patient (PhysioNet RECORDS)")]
json.dump(res, open(os.path.join(ROOT, "revision/results/ptb_patient_group.json"), "w"), indent=1)
