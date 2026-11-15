"""Diagnostic for aami_dechazal_ld.py: which classifier settings (class-weighted covariance on/off, equal vs empirical priors) bring the
re-implementation closer to the paper's DS1 record-wise CV targets for configuration XI (accuracy 86.2%, SVEB 54.7, VEB 40.0, F 26.0)."""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import aami_dechazal_ld as dz, aami_experiment as ae

class LD(dz.WLD):
    def fit(self, X, y, classes, target=400, weighted=True, empirical_priors=False):
        self.classes = classes; self.mu = {}; num = np.zeros((X.shape[1],) * 2); den = 0.0; ns = []
        for c in classes:
            Xc = X[y == c]; n = len(Xc); ns.append(n); w = (target / n if (weighted and n > target) else 1.0)
            self.mu[c] = Xc.mean(0); d = Xc - self.mu[c]; num += w * d.T @ d; den += w * n
        self.P = np.linalg.pinv(num / den)
        pri = np.array(ns, float) / sum(ns) if empirical_priors else np.ones(len(classes)) / len(classes)
        self.lp = np.log(pri); return self
    def posterior(self, X):
        d = np.stack([X @ self.P @ self.mu[c] - 0.5 * self.mu[c] @ self.P @ self.mu[c] + self.lp[k] for k, c in enumerate(self.classes)], 1)
        d -= d.max(1, keepdims=True); p = np.exp(d); return p / p.sum(1, keepdims=True)

data = {r: dz.record_features(r) for r in ae.DS1}
A = np.vstack([data[r][0] for r in ae.DS1]); B = np.vstack([data[r][1] for r in ae.DS1])
y = np.concatenate([data[r][2] for r in ae.DS1]); g = np.concatenate([[r] * len(data[r][2]) for r in ae.DS1])
print("paper targets (config XI, DS1 record-wise CV): acc 86.2  SVEB 54.7  VEB 40.0  F 26.0")
for weighted in (True, False):
    for emp in (False, True):
        yp = np.empty(len(y), dtype=object)
        for r in ae.DS1:
            te = g == r; posts = []
            for X in (A, B):
                tr_, te_ = X[~te], X[te]; mu, sd = tr_.mean(0), tr_.std(0) + 1e-9
                posts.append(LD().fit((tr_ - mu) / sd, y[~te], ae.CLASSES, weighted=weighted, empirical_priors=emp).posterior((te_ - mu) / sd))
            yp[te] = np.array(ae.CLASSES)[np.prod(posts, axis=0).argmax(1)]
        m = ae.metrics(list(y), list(yp)); pc = m["per_class"]
        print(f"weighted={weighted!s:5} empirical_priors={emp!s:5} acc {m['accuracy']:.1f}  sens N {pc['Normal']['sensitivity']:.1f} S {pc['SVEB']['sensitivity']:.1f} V {pc['VEB']['sensitivity']:.1f} F {pc['F']['sensitivity']:.1f}", flush=True)
