"""[RE-SEEDED at env NDIM, caches suffixed _d<NDIM>] Replicates PhysioNetLoader.load_dataset (return_rhythm=True) but also stores the per-beat R-R interval and
the whole-record / causal medians, plus the encoded HV. Cache -> revision/cache/physionet_cache.npz"""
import os, sys, numpy as np
from scipy.io import loadmat
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from src.config import SHDEConfig
SHDEConfig.D = int(os.environ.get("NDIM", 4096)); SFX = "" if SHDEConfig.D == 4096 else f"_d{SHDEConfig.D}"  # re-seeded re-encode at D=NDIM
from src.tokenizer import DeltaTokenizer
from src.hdc_encoding import HDCEncoder
from src.data_loader import PhysioNetLoader
DATA = sys.argv[1]
ld = PhysioNetLoader(DATA); cfg = SHDEConfig(); tok = DeltaTokenizer(thresholds=[0.05, 0.25, 0.6]); enc = HDCEncoder(cfg)
tr = {'N': 'Normal', 'A': 'AFib', 'O': 'Other_Anomaly', '~': 'Noisy'}
HV, Y, G, RR, MW, MC, MC8 = [], [], [], [], [], [], []
files = [f for f in os.listdir(DATA) if f.endswith('.mat')]
ds, half = 4, ld.half_window
for n, fn in enumerate(files):
    rid = fn[:-4]; label = tr.get(ld.reference_map.get(rid, 'N'), 'Normal')
    try:
        sig = np.nan_to_num(loadmat(os.path.join(DATA, fn))['val'][0].astype(float))[::ds]
        thr = np.max(sig) * 0.6; peaks = np.where(sig > thr)[0]; vp, last = [], -1000
        for p in peaks:
            if p - last > 200 // ds: vp.append(p); last = p
        if not vp: continue
        rr = np.diff(vp, prepend=vp[0]); pos = rr[rr > 0]; med_w = float(np.median(pos)) if len(pos) else None
        k = 0
        for i, p in enumerate(vp):
            if k >= 15: break
            if half <= p < len(sig) - half:
                w = sig[p - half:p + half]; w = w - np.mean(w); pv = np.percentile(np.abs(w), 98)
                if pv > 0: w = np.clip(w, -pv, pv) / pv
                hist = rr[1:i]; hist = hist[hist > 0]
                mc = float(np.median(hist)) if len(hist) else None
                mc8 = float(np.median(hist[-8:])) if len(hist) else None
                HV.append(np.packbits(enc.encode_sequence(tok.encode(w)).astype(np.uint8)))
                Y.append(label); G.append(rid); RR.append(float(rr[i]) if i > 0 else np.nan)
                MW.append(med_w if med_w else np.nan); MC.append(mc if mc else np.nan); MC8.append(mc8 if mc8 else np.nan); k += 1
    except Exception:
        pass
    if n % 1000 == 0: print(n, len(files), len(Y), flush=True)
np.savez_compressed(os.path.join(ROOT, f"revision/cache/physionet_cache{SFX}.npz"), hv=np.array(HV), y=np.array(Y), g=np.array(G),
                    rr=np.array(RR), mw=np.array(MW), mc=np.array(MC), mc8=np.array(MC8))
print("done beats", len(Y), "records", len(set(G)))
