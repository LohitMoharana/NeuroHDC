import json, numpy as np, os
R = os.path.join(os.path.dirname(__file__), "results")
names = ["off", "base", "causal", "causal8", "pt_whole", "pt_causal", "pt_causal8"]
d = {n: json.load(open(f"{R}/rr_{n}.json")) for n in names}
b = d["base"]
out = ["| variant | acc mean±sd | macro-F1 mean±sd | ΔF1 vs base (per fold 1..5) | ΔF1 mean | folds F1 up/5 | ΔAcc mean |", "|---|---|---|---|---|---|---|"]
for n in names:
    x = d[n]
    df = [f["macro_f1"] - g["macro_f1"] for f, g in zip(x["folds"], b["folds"])]
    da = [f["acc"] - g["acc"] for f, g in zip(x["folds"], b["folds"])]
    out.append(f"| {n} | {x['acc_mean']:.2f}±{x['acc_std']:.2f} | {x['f1_mean']:.2f}±{x['f1_std']:.2f} | "
               + " ".join(f"{v:+.2f}" for v in df) + f" | {np.mean(df):+.2f} | {sum(v>0 for v in df)} | {np.mean(da):+.2f} |")
out.append("")
out.append("Pooled per-class F1 (all 5 test folds pooled):")
out.append("| variant | " + " | ".join(sorted(b["pooled_per_class_f1"])) + " |")
out.append("|---|" + "---|" * 5)
for n in names:
    p = d[n]["pooled_per_class_f1"]
    out.append(f"| {n} | " + " | ".join(f"{p[k]:.2f}" for k in sorted(p)) + " |")
out.append("")
out.append("R-R bucket distribution (% of beats): " + "; ".join(f"{n}: {d[n]['bucket_pct']}" for n in names[1:]))
s = "\n".join(out); print(s.encode("ascii","replace").decode()); open(f"{R}/rr_summary.md", "w", encoding="utf8").write(s)
