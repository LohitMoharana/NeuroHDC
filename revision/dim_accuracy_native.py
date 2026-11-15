"""RE-SEEDED variant (caches re-encoded at D=N; no truncation). Original description: Accuracy vs hypervector dimension on MIT-BIH (submitted protocol, rhythm ON, whole-record median): the cached D=4096
hypervectors are truncated to the first N bits (a valid N-dim encoding because dimensions are generated independently;
NOT a re-seeded re-encode) and the rhythm codebook is redrawn at size N. N=4096 must reproduce 70.99/35.77.
Usage: python revision/dim_accuracy.py <N>   -> revision/results/dim_accuracy_<N>.json"""
import os, sys, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import numpy as _np
_orig_load = _np.load
_N = int(next(a for a in sys.argv[1:] if a.isdigit() and int(a) in (1024, 2048)))
def _load(f, *a, **k):          # point the unchanged Data classes at the re-seeded D=N caches
    f = str(f)
    for base in ("mitbih_cache", "physionet_cache", "ptb_cache", "stt_cache"):
        if f.endswith(base + ".npz"): f = f[:-4] + f"_d{_N}.npz"
    return _orig_load(f, *a, **k)
_np.load = _load
import nested_experiment as ne
from sklearn.model_selection import StratifiedGroupKFold
N = int(sys.argv[1])
ne.SHDEConfig.D = N          # AssociativeMemory sizes its sums from config.D
D = ne.Data(); D.D = N
rng = np.random.RandomState(ne.SEED)
D.codebook = {b: ne.rx.bipolar(rng.choice([-1, 1], size=N)) for b in ne.rx.BUCKETS}
kf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=ne.SEED)
p = dict(ne.BASE); accs, f1s = [], []
for fold, (tr, te) in enumerate(kf.split(np.zeros(len(D.y)), D.y, groups=D.groups)):
    yt, yp = ne.fit_predict(D, tr, te, p, ne.SEED + fold)
    accs.append(100 * float(np.mean(np.array(yt) == np.array(yp)))); f1s.append(ne.macro_f1(yt, yp))
    print(N, "fold", fold + 1, round(accs[-1], 2), round(f1s[-1], 2), flush=True)
res = dict(D=N, acc=f"{np.mean(accs):.2f}+-{np.std(accs):.2f}", f1=f"{np.mean(f1s):.2f}+-{np.std(f1s):.2f}",
           fold_acc=[round(a, 2) for a in accs], fold_f1=[round(f, 2) for f in f1s])
print("FINAL", res); json.dump(res, open(os.path.join(os.path.dirname(__file__), "results", f"dim_accuracy_native_{N}.json"), "w"), indent=1)
