"""Why does LBBB fail? Fold composition of the paper's StratifiedGroupKFold (seed 42), MIT-BIH, from the cache."""
import os, json, numpy as np
from sklearn.model_selection import StratifiedGroupKFold
R = os.path.dirname(__file__)
c = np.load(os.path.join(R, "cache", "mitbih_cache.npz"), allow_pickle=True)
y, g = c["y"], c["groups"]
base = json.load(open(os.path.join(R, "results", "rr_base.json")))
kf = StratifiedGroupKFold(5, shuffle=True, random_state=42)
out = []
classes = ["Normal", "PVC", "PAC", "LBBB", "RBBB"]
out.append("Records containing each class (whole dataset): " + "; ".join(
    f"{k}: {len(set(g[y==k]))} records / {int((y==k).sum())} beats" for k in classes))
out.append("")
out.append("| fold | test records w/ LBBB (beats) | LBBB beats in TRAIN | fold F1 (acc) | LBBB F1 | PAC F1 | PVC F1 | RBBB F1 |")
out.append("|---|---|---|---|---|---|---|---|")
for f, (tr, te) in enumerate(kf.split(np.zeros(len(y)), y, groups=g)):
    lt = te[y[te] == "LBBB"]
    recs = sorted(set(g[lt]))
    ltr = int((y[tr] == "LBBB").sum())
    pf = base["folds"][f]["per_class_f1"]
    out.append(f"| {f+1} | {len(recs)} ({len(lt)}) {recs} | {ltr} | {base['folds'][f]['macro_f1']:.2f} ({base['folds'][f]['acc']:.2f}) | "
               f"{pf.get('LBBB',float('nan')):.2f} | {pf.get('PAC',float('nan')):.2f} | {pf.get('PVC',float('nan')):.2f} | {pf.get('RBBB',float('nan')):.2f} |")
s = "\n".join(out); print(s); open(os.path.join(R, "results", "lbbb_fold_analysis.md"), "w", encoding="utf8").write(s)
