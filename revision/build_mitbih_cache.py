"""Cache MIT-BIH beats exactly as scripts/01_train_python.py loads them (same loader,
same record order, same tokenizer/encoder), so rhythm variants can be re-run quickly.
Writes revision/cache/mitbih_cache.npz (git-ignored). Read-only w.r.t. the dataset.

Usage: python revision/build_mitbih_cache.py <path to Datasets/MIT-BIH>
"""
import os, sys, time
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from src.config import SHDEConfig
from src.tokenizer import DeltaTokenizer
from src.hdc_encoding import HDCEncoder
from src.data_loader import MITBIHLoader

data_dir = sys.argv[1]
out_dir = os.path.join(ROOT, "revision", "cache")
os.makedirs(out_dir, exist_ok=True)

cfg, tok = SHDEConfig(), DeltaTokenizer(thresholds=[0.05, 0.25, 0.6])
enc = HDCEncoder(cfg)
loader = MITBIHLoader(data_dir)
records = sorted(f.replace(".csv", "") for f in os.listdir(data_dir) if f.endswith(".csv"))

y, groups, peaks, hv_bits = [], [], [], []
zero_tok = tot_tok = 0
t0 = time.time()
for rec in records:
    if not os.path.exists(os.path.join(data_dir, f"{rec}annotations.txt")):
        continue
    X, yy, pk = loader.load_record(rec, return_peaks=True)
    for w in X:
        sp = tok.encode(w)
        zero_tok += int((sp == 0).sum()); tot_tok += sp.size
        hv_bits.append(np.packbits(enc.encode_sequence(sp).astype(np.uint8)))
    y += list(yy); groups += [rec] * len(yy); peaks += list(pk)
    print(f"{rec}: {len(yy)} beats  ({time.time()-t0:.0f}s)", flush=True)

np.savez_compressed(os.path.join(out_dir, "mitbih_cache.npz"),
                    hv=np.array(hv_bits), y=np.array(y), groups=np.array(groups),
                    peaks=np.array(peaks), D=cfg.D)
print(f"total beats {len(y)}, records {len(set(groups))}, zero-token rate {100*zero_tok/tot_tok:.3f}%")
