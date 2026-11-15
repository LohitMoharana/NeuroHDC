"""AAMI four-class (N, S, V, F) inter-patient evaluation of NeuroHDC on MIT-BIH (revision preparation only; NOT part of the
submitted paper).

Protocol (De Chazal-style inter-patient paradigm; lists verified against Guo et al., arXiv 1810.04121, which use the same 22+22 split):
  train DS1 = 101 106 108 109 112 114 115 116 118 119 122 124 201 203 205 207 208 209 215 220 223 230
  test  DS2 = 100 103 105 111 113 117 121 123 200 202 210 212 213 214 219 221 222 228 231 232 233 234
  excluded (paced): 102 104 107 217.  Q (unclassifiable/paced/fusion-of-paced) beats are dropped from train AND test (4-class setup).
Beat-symbol -> AAMI class: N = N L R e j | S = A a J S | V = V E | F = F | Q = / f Q (dropped). Non-beat annotations ignored.
Pipeline = the submitted one: 256-sample window centred on the annotated R peak, per-window mean removal and 98th-percentile
clip/scale (same as MITBIHLoader), delta tokenizer [0.05,0.25,0.6], D=4096 HDC encoder (seed 42), one-shot prototypes +
30-epoch refinement (LR 15 decaying), caps 12000 (N) / 3000 (others), R-R bucket binding (0.85/1.15) with whole-record median
(`rhythm=whole`, as submitted) or without (`rhythm=off`). No hyper-parameter is tuned on DS2.
Repeats: the only randomness is training-sample choice/order, so 5 seeds (42..46) are run and mean +- std reported.

Usage: python revision/aami_experiment.py <rhythm: off|whole|causal8> [D=4096]
"""
import os, sys, json, time
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
from src.config import SHDEConfig
from src.tokenizer import DeltaTokenizer
from src.hdc_encoding import HDCEncoder
import rr_experiment as rx
import nested_experiment as ne
from sklearn.metrics import confusion_matrix

DATA = "D:/Projects/Personal/NeuroHDC/Datasets/MIT-BIH"
DS1 = [101, 106, 108, 109, 112, 114, 115, 116, 118, 119, 122, 124, 201, 203, 205, 207, 208, 209, 215, 220, 223, 230]
DS2 = [100, 103, 105, 111, 113, 117, 121, 123, 200, 202, 210, 212, 213, 214, 219, 221, 222, 228, 231, 232, 233, 234]
CLASS_OF = {**{s: "Normal" for s in "NLRej"}, **{s: "SVEB" for s in "AaJS"}, **{s: "VEB" for s in "VE"}, "F": "F",
            **{s: "Q" for s in ["/", "f", "Q"]}}
CLASSES = ["Normal", "SVEB", "VEB", "F"]
SEEDS = [42, 43, 44, 45, 46]
CACHE = os.path.join(ROOT, "revision", "cache", "aami_cache.npz")


def parse(txt):
    out = []
    for line in open(txt).readlines()[1:]:
        p = line.split()
        if len(p) >= 3:
            try: out.append((int(p[1]), p[2]))
            except ValueError: pass
    return out


def build_cache():
    cfg = SHDEConfig(); tok = DeltaTokenizer(thresholds=[0.05, 0.25, 0.6]); enc = HDCEncoder(cfg)
    half = cfg.WINDOW_SIZE // 2
    hv, y, grp, ratio, ratio8, split, counts = [], [], [], [], [], [], {}
    t0 = time.time()
    for rec, part in [(r, "train") for r in DS1] + [(r, "test") for r in DS2]:
        csv = os.path.join(DATA, f"{rec}.csv"); ann = os.path.join(DATA, f"{rec}annotations.txt")
        sig = pd.read_csv(csv).iloc[:, 1].values
        beats = [(s, CLASS_OF[b]) for s, b in parse(ann) if b in CLASS_OF]      # every real beat, Q included, for R-R
        samples = np.array([s for s, _ in beats])
        rr = np.diff(samples, prepend=samples[0]); pos = rr[rr > 0]
        med = float(np.median(pos)) if len(pos) else None                       # whole-record median (as submitted)
        for i, (s, c) in enumerate(beats):
            if c == "Q" or s < half or s > len(sig) - half:
                continue
            w = sig[s - half:s + half] - np.mean(sig[s - half:s + half])
            pv = np.percentile(np.abs(w), 98)
            if pv > 0: w = np.clip(w, -pv, pv) / pv
            hv.append(np.packbits(enc.encode_sequence(tok.encode(w)).astype(np.uint8)))
            y.append(c); grp.append(rec); split.append(part)
            ratio.append(rr[i] / med if (i > 0 and med and med > 0) else np.nan)
            m8 = rx.median_ref(rr, i, "causal8")                       # median of the last <=8 strictly preceding intervals
            ratio8.append(rr[i] / m8 if (i > 0 and m8 and m8 > 0) else np.nan)
            counts[(part, c)] = counts.get((part, c), 0) + 1
        print(f"{rec} done ({time.time()-t0:.0f}s)", flush=True)
    np.savez_compressed(CACHE, hv=np.array(hv), y=np.array(y), groups=np.array(grp), ratio=np.array(ratio), ratio8=np.array(ratio8), split=np.array(split))
    print("counts", {f"{k[0]}:{k[1]}": v for k, v in sorted(counts.items())})


class AData:
    def __init__(self, D_override=None):
        c = np.load(CACHE, allow_pickle=True)
        self.y, self.groups, self.ratio, self.split, self._hv = c["y"], c["groups"], c["ratio"], c["split"], c["hv"]
        self.ratio8 = c["ratio8"]
        self.D = 4096
        rng = np.random.RandomState(ne.SEED)
        self.codebook = {b: rx.bipolar(rng.choice([-1, 1], size=self.D)) for b in rx.BUCKETS}
    def hv(self, tok, idx):
        return np.unpackbits(self._hv[idx], axis=1)[:, :self.D].astype(np.int8)
    def buckets(self, idx, short, long):
        r = self.ratio[idx]; out = np.full(len(idx), "NORMAL", dtype=object); ok = ~np.isnan(r)
        out[ok & (r < short)] = "SHORT"; out[ok & (r > long)] = "LONG"
        return out


def metrics(yt, yp):
    yt, yp = np.array(yt), np.array(yp)
    cm = confusion_matrix(yt, yp, labels=CLASSES)
    res = {"accuracy": 100 * float(np.trace(cm) / cm.sum()), "per_class": {}}
    f1s = []
    for k, c in enumerate(CLASSES):
        tp = cm[k, k]; fn = cm[k].sum() - tp; fp = cm[:, k].sum() - tp; tn = cm.sum() - tp - fn - fp
        sens = tp / (tp + fn) if tp + fn else float("nan"); ppv = tp / (tp + fp) if tp + fp else float("nan")
        f1 = 2 * sens * ppv / (sens + ppv) if (sens + ppv) and not np.isnan(sens + ppv) else 0.0
        res["per_class"][c] = dict(sensitivity=100 * sens, ppv=100 * ppv, f1=100 * f1, fpr=100 * fp / (fp + tn) if fp + tn else float("nan"),
                                   support=int(tp + fn))
        f1s.append(f1)
    res["macro_f1"] = 100 * float(np.mean(f1s)); res["confusion"] = cm.tolist()
    return res


def main():
    rhythm = sys.argv[1]
    assert rhythm in ("off", "whole", "causal8")
    if not os.path.exists(CACHE): build_cache()
    D = AData()
    if rhythm == "causal8": D.ratio = D.ratio8
    if rhythm == "off": D.ratio = np.full(len(D.y), np.nan)      # every beat NORMAL bucket; see below
    tr = np.where(D.split == "train")[0]; te = np.where(D.split == "test")[0]
    assert not (set(D.groups[tr]) & set(D.groups[te]))
    print("train", len(tr), {c: int((D.y[tr] == c).sum()) for c in CLASSES}, "test", len(te), {c: int((D.y[te] == c).sum()) for c in CLASSES})
    p = dict(ne.BASE)
    runs = []
    for sd in SEEDS:
        if rhythm == "off":
            # binding with a constant bucket would still XOR a fixed vector; use identity binding by skipping the bind step
            ne.bind = lambda Dd, h, b: h
        yt, yp = ne.fit_predict(D, tr, te, p, sd)
        m = metrics(yt, yp); m["seed"] = sd; runs.append(m)
        pc = m["per_class"]
        print(f"seed {sd}: acc {m['accuracy']:.2f} macroF1 {m['macro_f1']:.2f} | " + " ".join(f"{c} sens {pc[c]['sensitivity']:.1f} ppv {pc[c]['ppv']:.1f}" for c in CLASSES), flush=True)
    agg = {"rhythm": rhythm, "D": 4096, "seeds": SEEDS, "train_counts": {c: int((D.y[tr] == c).sum()) for c in CLASSES},
           "test_counts": {c: int((D.y[te] == c).sum()) for c in CLASSES}, "runs": runs}
    for key in ("accuracy", "macro_f1"):
        v = [r[key] for r in runs]; agg[key] = f"{np.mean(v):.2f}+-{np.std(v):.2f}"
    for c in CLASSES:
        for key in ("sensitivity", "ppv", "f1", "fpr"):
            v = [r["per_class"][c][key] for r in runs]; agg[f"{c}_{key}"] = f"{np.nanmean(v):.2f}+-{np.nanstd(v):.2f}"
    json.dump(agg, open(os.path.join(ROOT, "revision", "results", f"aami_{rhythm}.json"), "w"), indent=1)
    print("FINAL", {k: v for k, v in agg.items() if k not in ("runs",)})


if __name__ == "__main__":
    main()
