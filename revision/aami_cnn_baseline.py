"""1D-CNN baseline (the paper's ECG_1D_CNN from scripts/03_train_baselines.py, copied verbatim in structure) on the SAME AAMI
four-class inter-patient split as aami_experiment.py: train DS1, test DS2, caps 12000 (N) / 3000 (others), 15 epochs, batch 64,
Adam lr 1e-3, seeds 42..46. Input: the same 256-sample normalised window (no rhythm feature). Revision preparation only."""
import os, sys, json
import numpy as np, pandas as pd
import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
sys.path.insert(0, os.path.dirname(__file__))
import aami_experiment as ae

class ECG_1D_CNN(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        self.conv1 = nn.Conv1d(1, 16, kernel_size=7, padding=3); self.relu1 = nn.ReLU(); self.pool1 = nn.MaxPool1d(2)
        self.conv2 = nn.Conv1d(16, 32, kernel_size=5, padding=2); self.relu2 = nn.ReLU(); self.pool2 = nn.MaxPool1d(2)
        self.flatten = nn.Flatten(); self.fc1 = nn.Linear(32 * 64, 128); self.relu3 = nn.ReLU(); self.fc2 = nn.Linear(128, num_classes)
    def forward(self, x):
        x = self.pool1(self.relu1(self.conv1(x))); x = self.pool2(self.relu2(self.conv2(x)))
        return self.fc2(self.relu3(self.fc1(self.flatten(x))))

half = 128
def windows(recs, part):
    X, y = [], []
    for rec in recs:
        sig = pd.read_csv(os.path.join(ae.DATA, f"{rec}.csv")).iloc[:, 1].values
        for s, b in ae.parse(os.path.join(ae.DATA, f"{rec}annotations.txt")):
            if b not in ae.CLASS_OF or ae.CLASS_OF[b] == "Q" or s < half or s > len(sig) - half: continue
            w = sig[s - half:s + half] - np.mean(sig[s - half:s + half]); pv = np.percentile(np.abs(w), 98)
            if pv > 0: w = np.clip(w, -pv, pv) / pv
            X.append(w); y.append(ae.CLASS_OF[b])
    return np.array(X, dtype=np.float32), np.array(y)
Xtr, ytr = windows(ae.DS1, "train"); Xte, yte = windows(ae.DS2, "test")
print("train", len(ytr), "test", len(yte))
ci = {c: i for i, c in enumerate(ae.CLASSES)}; dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
runs = []
for sd in ae.SEEDS:
    rng = np.random.RandomState(sd); torch.manual_seed(sd); sel = []
    for c in ae.CLASSES:
        idx = np.where(ytr == c)[0]; rng.shuffle(idx); sel += list(idx[: (12000 if c == "Normal" else 3000)])
    Xt = torch.tensor(Xtr[sel]).unsqueeze(1); yt = torch.tensor([ci[c] for c in ytr[sel]])
    model = ECG_1D_CNN(len(ae.CLASSES)).to(dev); opt = optim.Adam(model.parameters(), lr=0.001); lossf = nn.CrossEntropyLoss()
    for ep in range(15):
        model.train()
        for bx, by in DataLoader(TensorDataset(Xt, yt), batch_size=64, shuffle=True):
            bx, by = bx.to(dev), by.to(dev); opt.zero_grad(); lossf(model(bx), by).backward(); opt.step()
    model.eval()
    with torch.no_grad(): pr = model(torch.tensor(Xte).unsqueeze(1).to(dev)).argmax(1).cpu().numpy()
    m = ae.metrics(list(yte), [ae.CLASSES[i] for i in pr]); m["seed"] = sd; runs.append(m); pc = m["per_class"]
    print(f"seed {sd}: acc {m['accuracy']:.2f} macroF1 {m['macro_f1']:.2f} | " + " ".join(f"{c} sens {pc[c]['sensitivity']:.1f} ppv {pc[c]['ppv']:.1f}" for c in ae.CLASSES), flush=True)
agg = {"model": "1D-CNN (paper baseline)", "seeds": ae.SEEDS, "runs": runs}
for key in ("accuracy", "macro_f1"):
    v = [r[key] for r in runs]; agg[key] = f"{np.mean(v):.2f}+-{np.std(v):.2f}"
for c in ae.CLASSES:
    for key in ("sensitivity", "ppv", "f1", "fpr"):
        v = [r["per_class"][c][key] for r in runs]; agg[f"{c}_{key}"] = f"{np.nanmean(v):.2f}+-{np.nanstd(v):.2f}"
json.dump(agg, open(os.path.join(os.path.dirname(__file__), "results", "aami_cnn.json"), "w"), indent=1)
print("FINAL", {k: v for k, v in agg.items() if k != "runs"})
