"""HV cache for an alternative tokenizer-threshold triple (same beats/order as mitbih_cache.npz).
Usage: python revision/build_tok_cache.py <Datasets/MIT-BIH> <name> t1 t2 t3"""
import os, sys
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from src.config import SHDEConfig
from src.tokenizer import DeltaTokenizer
from src.hdc_encoding import HDCEncoder
from src.data_loader import MITBIHLoader

data_dir, name = sys.argv[1], sys.argv[2]
th = [float(v) for v in sys.argv[3:6]]
base = np.load(os.path.join(ROOT, "revision", "cache", "mitbih_cache.npz"))
cfg, tok, enc = SHDEConfig(), DeltaTokenizer(thresholds=th), None
enc = HDCEncoder(cfg)
loader = MITBIHLoader(data_dir)
y, hv, zt, tt = [], [], 0, 0
for rec in list(dict.fromkeys(base["groups"])):
    X, yy, _ = loader.load_record(rec, return_peaks=True)
    for w in X:
        sp = tok.encode(w)
        zt += int((sp == 0).sum()); tt += sp.size
        hv.append(np.packbits(enc.encode_sequence(sp).astype(np.uint8)))
    y += list(yy)
assert np.array_equal(np.array(y), base["y"]), "beat order differs from base cache"
np.savez_compressed(os.path.join(ROOT, "revision", "cache", f"tok_{name}.npz"), hv=np.array(hv), thresholds=th)
print(f"{name} {th}: beats {len(y)}, zero-token rate {100*zt/tt:.3f}%")
