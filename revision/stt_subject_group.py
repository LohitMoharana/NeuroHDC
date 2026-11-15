"""ST-T: grouped by record (as submitted) vs by clinical-header signature (proxy for subject; no official mapping offline). Same loader, encoder, caps,
refinement loop, StratifiedGroupKFold(5, shuffle, seed 42) as scripts/01_train_python.py (no rhythm)."""
import os, sys, json, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from src.config import SHDEConfig
from src.tokenizer import DeltaTokenizer
from src.hdc_encoding import HDCEncoder
from src.associative_mem import AssociativeMemory
from src.data_loader import STTLoader
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score

DATA = sys.argv[1]
SEED, MAXN, MAXA, EPOCHS = 42, 12000, 3000, 30
cfg = SHDEConfig(); tok = DeltaTokenizer(thresholds=[0.05, 0.25, 0.6]); enc = HDCEncoder(cfg)
np.random.seed(SEED)  # loader shuffles with the global RNG (unseeded in the submitted script)
X, y, g = STTLoader(DATA).load_dataset()
y, g = np.array(y), np.array(g)
def sig_of(rec):
    com = [l.strip() for l in open(os.path.join(DATA, rec + ".hea"), errors="ignore") if l.startswith("#")]
    return "|".join(c for c in com if not c.lower().startswith("#recorder"))
sigs = {r: sig_of(str(r)) for r in set(g)}
pat = np.array([sigs[str(n)] for n in g])
# OFFICIAL same-subject groups, from the PhysioNet European ST-T page (https://physionet.org/content/edb/1.0.0/):
# "Records e0118-e0122 come from the same subject; also records e0123-e0126, e0129 and e0133, e0136 and e0139,
#  e0147 and e0148, e0154 and e0155, and e0162 and e0163." (90 records, 79 subjects; there is no e0120 file.)
OFFICIAL = [["e0118", "e0119", "e0121", "e0122"], ["e0123", "e0124", "e0125", "e0126"], ["e0129", "e0133"],
            ["e0136", "e0139"], ["e0147", "e0148"], ["e0154", "e0155"], ["e0162", "e0163"]]
rec2subj = {r: "S_" + grp[0] for grp in OFFICIAL for r in grp}
off = np.array([rec2subj.get(str(n), str(n)) for n in g])
print("official subject groups among loaded records:", len(set(off)))
print("beats", len(y), "classes", {k: int((y == k).sum()) for k in np.unique(y)}, "file-groups", len(set(g)), "signature-groups", len(set(pat)))
hv = np.array([enc.encode_sequence(tok.encode(w)) for w in X], dtype=np.int8)
bip = lambda v: np.where(np.asarray(v) > 0, 1, -1).astype(np.int32)

def run(groups, name):
    kf = StratifiedGroupKFold(5, shuffle=True, random_state=SEED)
    accs, f1s, leak = [], [], []
    for fold, (tr, te) in enumerate(kf.split(np.zeros(len(y)), y, groups=groups)):
        assert not (set(groups[tr]) & set(groups[te]))
        leak.append(len(set(off[tr]) & set(off[te])))      # patients appearing in both train and test
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
             fold_f1=[round(v, 2) for v in f1s], signature_groups_in_both_train_and_test_per_fold=leak)
    print(r, flush=True); return r
res = [run(g, "record (as submitted)"), run(off, "OFFICIAL subject (PhysioNet page)"), run(pat, "clinical-header signature (proxy)")]
json.dump(res, open(os.path.join(ROOT, "revision/results/stt_subject_group.json"), "w"), indent=1)
