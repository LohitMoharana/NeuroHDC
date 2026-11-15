"""Accuracy vs hypervector dimension on PhysioNet / PTB / ST-T (submitted protocol and caps): cached D=4096 hypervectors
truncated to the first N bits (valid N-dim encoding because dimensions are generated independently; NOT a re-seeded re-encode);
PhysioNet keeps the submitted whole-record-median rhythm binding with a codebook redrawn at size N. N=4096 must reproduce
the re-run baselines (PhysioNet 45.05, PTB 56.24, ST-T 78.51). Usage: python revision/dim_accuracy_other.py <pn|ptb|stt> <N>"""
import os, sys, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
ds, N = sys.argv[1], int(sys.argv[2])
if ds == "pn":
    import nested_physionet as M
    D = M.Data()
else:
    import nested_generic as M
    D = M.Data(ds)
M.SHDEConfig.D = N                       # AssociativeMemory sizes its sums from config.D
D.hv = D.hv[:, :N]; D.D = N
if ds == "pn":
    rng = np.random.RandomState(M.SEED)
    D.cb = {b: M.bip(rng.choice([-1, 1], size=N)) for b in ["SHORT", "NORMAL", "LONG"]}
from sklearn.model_selection import StratifiedGroupKFold
kf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=M.SEED)
groups = D.g
p = dict(M.BASE); accs, f1s = [], []
for fold, (tr, te) in enumerate(kf.split(np.zeros(len(D.y)), D.y, groups=groups)):
    yt, yp = M.fit_predict(D, tr, te, p, M.SEED + fold)
    accs.append(100 * float(np.mean(np.array(yt) == np.array(yp)))); f1s.append(M.macro_f1(yt, yp))
    print(ds, N, "fold", fold + 1, round(accs[-1], 2), round(f1s[-1], 2), flush=True)
res = dict(dataset=ds, D=N, acc=f"{np.mean(accs):.2f}+-{np.std(accs):.2f}", f1=f"{np.mean(f1s):.2f}+-{np.std(f1s):.2f}",
           fold_f1=[round(f, 2) for f in f1s], fold_acc=[round(a, 2) for a in accs])
print("FINAL", res)
json.dump(res, open(os.path.join(os.path.dirname(__file__), "results", f"dim_accuracy_{ds}_{N}.json"), "w"), indent=1)
