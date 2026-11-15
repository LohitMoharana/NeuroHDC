"""Pan-Tompkins (1985) QRS detector (own implementation; no external ECG package installed)
+ evaluation against MIT-BIH annotations. Offline use for the revision-prep R-R sensitivity test.

Pipeline: 5-15 Hz band-pass (causal Butterworth) -> 5-point derivative -> squaring ->
150 ms moving-window integration -> adaptive dual thresholds (SPKI/NPKI), 200 ms refractory,
T-wave slope rejection (<360 ms), search-back (1.66 x RR_avg). R location is then refined
on the band-passed / raw signal.

CLI: python revision/pan_tompkins.py <Datasets/MIT-BIH>   -> writes revision/cache/pt_peaks.npz
"""
import os, sys
import numpy as np
import pandas as pd
from scipy.signal import butter, lfilter

FS = 360
TOL = int(0.150 * FS)  # 150 ms matching tolerance (AAMI/EC57 convention)
BEAT_SYMS = set("NLRBAaJSVrFejnE/fQ?")  # WFDB beat annotation symbols


def detect(x, fs=FS):
    x = np.asarray(x, dtype=float)
    x = x - np.median(x)
    b, a = butter(2, [5 / (fs / 2), 15 / (fs / 2)], btype="band")
    bp = lfilter(b, a, x)
    d = np.zeros_like(bp)
    d[2:-2] = (-bp[:-4] - 2 * bp[1:-3] + 2 * bp[3:-1] + bp[4:]) / 8.0
    sq = d ** 2
    w = int(0.150 * fs)
    mwi = np.convolve(sq, np.ones(w) / w, mode="full")[: len(sq)]

    # candidate peaks = local maxima of MWI
    cand = np.nonzero((mwi[1:-1] > mwi[:-2]) & (mwi[1:-1] >= mwi[2:]))[0] + 1

    n0 = min(len(mwi), 2 * fs)
    spki, npki = 0.25 * mwi[:n0].max(), 0.5 * mwi[:n0].mean()
    thr1 = npki + 0.25 * (spki - npki)
    refr, twin = int(0.200 * fs), int(0.360 * fs)
    qrs, qrs_slope = [], []
    rr_recent, last_unaccepted = [], []

    def slope(p):
        lo = max(0, p - w)
        return d[lo:p + 1].max() if p > lo else 0.0

    for p in cand:
        pk = mwi[p]
        # search-back if we have been silent for too long
        if len(qrs) >= 2 and rr_recent:
            rr_avg = np.mean(rr_recent[-8:])
            if p - qrs[-1] > 1.66 * rr_avg:
                thr2 = 0.5 * thr1
                sb = [c for c in last_unaccepted if c > qrs[-1] + refr and mwi[c] > thr2]
                if sb:
                    c = max(sb, key=lambda c: mwi[c])
                    qrs.append(c); qrs_slope.append(slope(c))
                    spki = 0.25 * mwi[c] + 0.75 * spki
                    rr_recent.append(qrs[-1] - qrs[-2])
        if pk > thr1:
            if qrs and p - qrs[-1] < refr:
                # inside refractory: keep the larger one
                if pk > mwi[qrs[-1]]:
                    qrs[-1], qrs_slope[-1] = p, slope(p)
                continue
            if qrs and p - qrs[-1] < twin and slope(p) < 0.5 * qrs_slope[-1]:
                npki = 0.125 * pk + 0.875 * npki  # T wave
                last_unaccepted.append(p)
            else:
                qrs.append(p); qrs_slope.append(slope(p))
                spki = 0.125 * pk + 0.875 * spki
                if len(qrs) >= 2:
                    rr_recent.append(qrs[-1] - qrs[-2])
        else:
            npki = 0.125 * pk + 0.875 * npki
            last_unaccepted.append(p)
        last_unaccepted = last_unaccepted[-30:]
        thr1 = npki + 0.25 * (spki - npki)

    # localise R: strongest band-passed deflection in the window preceding the MWI peak,
    # then snap to the raw-signal extremum within +-8 samples
    out = []
    for p in qrs:
        lo, hi = max(0, p - int(0.25 * fs)), min(len(bp), p + 6)
        r = lo + int(np.argmax(np.abs(bp[lo:hi])))
        lo2, hi2 = max(0, r - 12), min(len(x), r + 13)
        out.append(lo2 + int(np.argmax(np.abs(x[lo2:hi2] - np.median(x[lo2:hi2])))))
    out = np.array(sorted(set(out)), dtype=int)
    return out


def match(ref, det, tol=TOL):
    """Greedy one-to-one nearest matching. Returns det index per ref (or -1)."""
    det = np.asarray(det)
    idx = -np.ones(len(ref), dtype=int)
    used = set()
    for i, r in enumerate(ref):
        j = int(np.searchsorted(det, r))
        best = None
        for k in (j - 1, j):
            if 0 <= k < len(det) and abs(det[k] - r) <= tol and k not in used:
                if best is None or abs(det[k] - r) < abs(det[best] - r):
                    best = k
        if best is not None:
            idx[i] = best; used.add(best)
    return idx


def load_signal(data_dir, rec):
    df = pd.read_csv(os.path.join(data_dir, f"{rec}.csv"))
    return df[df.columns[1] if len(df.columns) > 1 else df.columns[0]].values


def parse_all_annotations(path):
    ann = []
    with open(path) as f:
        for line in f.readlines()[1:]:
            p = line.split()
            if len(p) >= 3:
                try:
                    ann.append((int(p[1]), p[2]))
                except ValueError:
                    pass
    return ann


if __name__ == "__main__":
    data_dir = sys.argv[1]
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cache = np.load(os.path.join(root, "revision", "cache", "mitbih_cache.npz"))
    groups, peaks = cache["groups"], cache["peaks"]
    recs = list(dict.fromkeys(groups))  # original record order
    det_all, tp = {}, 0
    tot_used = tot_beats = tot_det = tp_beats = 0
    for rec in recs:
        x = load_signal(data_dir, rec)
        det = detect(x)
        det_all[rec] = det
        used = peaks[groups == rec]
        ann_beats = np.array([s for s, c in parse_all_annotations(
            os.path.join(data_dir, f"{rec}annotations.txt")) if c in BEAT_SYMS])
        m_used = match(used, det)
        m_all = match(ann_beats, det) if len(ann_beats) else np.array([])
        tot_used += len(used); tp += int((m_used >= 0).sum())
        tot_beats += len(ann_beats); tp_beats += int((m_all >= 0).sum()); tot_det += len(det)
        print(f"{rec}: det={len(det):5d} annBeats={len(ann_beats):5d} usedBeats={len(used):5d} "
              f"usedMatched={(m_used>=0).sum():5d}", flush=True)
    print(f"\nSensitivity on the {tot_used} beats used in the benchmark (5 classes): {100*tp/tot_used:.2f}%")
    print(f"Sensitivity on all {tot_beats} annotated beats: {100*tp_beats/tot_beats:.2f}%  "
          f"PPV (matched annotated beats / detections): {100*tp_beats/tot_det:.2f}%  (tol {TOL} samples = 150 ms)")
    np.savez(os.path.join(root, "revision", "cache", "pt_peaks.npz"),
             **{f"rec_{k}": v for k, v in det_all.items()})
