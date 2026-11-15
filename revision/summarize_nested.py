import json, numpy as np, os
R = os.path.join(os.path.dirname(__file__), "results")
base = json.load(open(f"{R}/rr_base.json"))["folds"]
L = ["| family | acc mean±sd | macro-F1 mean±sd | ΔF1 vs submitted per fold | ΔF1 mean | ΔAcc mean | folds F1 up | folds w/ non-baseline pick |", "|---|---|---|---|---|---|---|---|"]
D = ["", "Per-fold selections (inner mean macro-F1 of winner vs submitted setting; outer test acc/F1):"]
for fam in ["schedule", "caps", "rhythm", "tokenizer"]:
    r = [json.load(open(f"{R}/nested_{fam}_f{k}.json")) for k in range(1, 6)]
    acc = [x["outer_acc"] for x in r]; f1 = [x["outer_macro_f1"] for x in r]
    d = [a - b["macro_f1"] for a, b in zip(f1, base)]; da = [a - b["acc"] for a, b in zip(acc, base)]
    L.append(f"| {fam} | {np.mean(acc):.2f}±{np.std(acc):.2f} | {np.mean(f1):.2f}±{np.std(f1):.2f} | " + " ".join(f"{v:+.2f}" for v in d)
             + f" | {np.mean(d):+.2f} | {np.mean(da):+.2f} | {sum(v>1e-9 for v in d)}/5 | {sum(x['selected']!=0 for x in r)}/5 |")
    for x in r:
        s = x["inner_scores"]
        D.append(f"- {fam} f{x['outer_fold']}: picked {x['selected_setting'] or 'submitted'}; inner {s[x['selected']]:.2f} vs submitted {s[0]:.2f} "
                 f"(inner gain {s[x['selected']]-s[0]:+.2f}); outer acc {x['outer_acc']:.2f}, F1 {x['outer_macro_f1']:.2f} "
                 f"(submitted fold F1 {base[x['outer_fold']-1]['macro_f1']:.2f}, delta {x['outer_macro_f1']-base[x['outer_fold']-1]['macro_f1']:+.2f})")
out = "\n".join(L + D)
print(out.encode("ascii", "replace").decode()); open(f"{R}/nested_summary.md", "w", encoding="utf8").write(out)
