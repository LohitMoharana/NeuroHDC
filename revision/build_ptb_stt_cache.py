"""Encode PTB and ST-T beats once (submitted tokenizer/encoder, no rhythm) -> revision/cache/{ptb,stt}_cache.npz.
Usage: python revision/build_ptb_stt_cache.py <ptb|stt> <data_dir>. STT loader shuffle uses np.random.seed(42)."""
import os, sys, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from src.config import SHDEConfig
from src.tokenizer import DeltaTokenizer
from src.hdc_encoding import HDCEncoder
from src.data_loader import PTBLoader, STTLoader
name, data = sys.argv[1], sys.argv[2]
np.random.seed(42)
X, y, g = (PTBLoader if name == "ptb" else STTLoader)(data).load_dataset()
cfg = SHDEConfig(); tok = DeltaTokenizer(thresholds=[0.05, 0.25, 0.6]); enc = HDCEncoder(cfg)
hv = np.array([np.packbits(enc.encode_sequence(tok.encode(w)).astype(np.uint8)) for w in X])
np.savez_compressed(os.path.join(ROOT, "revision", "cache", f"{name}_cache.npz"), hv=hv, y=np.array(y), g=np.array(g))
print(name, "beats", len(y), "records", len(set(g)), {k: int((np.array(y) == k).sum()) for k in set(y)})
