# -*- coding: utf-8 -*-
"""Probe: how does the 10426x1024 embedding cloud behave when squeezed to 3D?
Decides whether we can go PCA3 -> sphere directly, or need uniformization.
"""
import numpy as np, time, json, sys
from pathlib import Path

import os
TMP = Path(os.environ.get("SPHERE_INPUT", Path(__file__).resolve().parents[2] / "data" / "input"))
import os
OUT = Path(os.environ.get("SPHERE_OUT", Path(__file__).resolve().parents[2] / "out"))
OUT.mkdir(parents=True, exist_ok=True)

t0 = time.time()
ids, types, dates, rows = [], [], [], []
with open(TMP / "embeddings.tsv", "r", encoding="utf-8") as f:
    for line in f:
        a = line.rstrip("\n").split("\t")
        if len(a) < 4:
            continue
        ids.append(a[0]); types.append(a[1]); dates.append(a[2])
        rows.append(np.fromstring(a[3][1:-1], dtype=np.float32, sep=","))
E = np.vstack(rows)
print(f"loaded {E.shape} in {time.time()-t0:.1f}s  dtype={E.dtype}", flush=True)

# --- L2 check ---
nrm = np.linalg.norm(E, axis=1)
print(f"L2 norm: min={nrm.min():.4f} max={nrm.max():.4f} mean={nrm.mean():.4f}", flush=True)

# --- center + normalize ---
t1 = time.time()
mu = E.mean(axis=0)
X = E - mu
X /= np.linalg.norm(X, axis=1, keepdims=True)
print(f"centered+normalized in {time.time()-t1:.1f}s", flush=True)

# --- PCA via covariance eigendecomposition (1024x1024) ---
t2 = time.time()
C = X.T @ X
print(f"covariance {C.shape} in {time.time()-t2:.1f}s", flush=True)
t3 = time.time()
w, V = np.linalg.eigh(C.astype(np.float64))
order = np.argsort(w)[::-1]
w = w[order]; V = V[:, order]
ev = w / w.sum()
print(f"eigh in {time.time()-t3:.1f}s", flush=True)
print("top-10 explained var ratio: " + " ".join(f"{v*100:.1f}%" for v in ev[:10]), flush=True)
print(f"cum var @3={ev[:3].sum()*100:.1f}%  @16={ev[:16].sum()*100:.1f}%  @50={ev[:50].sum()*100:.1f}%", flush=True)

K = 50
Y = X @ V[:, :K].astype(np.float32)
print(f"proj to {K}d in {time.time()-t2:.1f}s", flush=True)

# --- 3D shape diagnostics ---
Y3 = Y[:, :3].astype(np.float64)
Y3 -= Y3.mean(0)
P = Y3 / np.linalg.norm(Y3, axis=1, keepdims=True)

z = P[:, 2]; lam = np.arctan2(P[:, 1], P[:, 0])
i = np.clip(((z + 1) / 2 * 32).astype(int), 0, 31)
j = np.clip(((lam + np.pi) / (2 * np.pi) * 32).astype(int), 0, 31)
b = i * 32 + j
cnt = np.bincount(b, minlength=1024)
print(f"PCA3 sphere binning: occupied={int((cnt>0).sum())}/1024  max_bin={cnt.max()}  mean={cnt.mean():.1f}", flush=True)
print(f"empty bins: {int((cnt==0).sum())}", flush=True)

# dispersion: how much of the sphere is really used? (spherical inertia)
print(f"spherical centroid |mean(P)| = {np.linalg.norm(P.mean(0)):.3f} (0=uniform, high=clumped)", flush=True)
# planarity check: are points near a great circle?
_, s, _ = np.linalg.svd(P, full_matrices=False)
print(f"singular values of 3D cloud: {s[0]:.1f} {s[1]:.1f} {s[2]:.1f} (ratio s2/s0={s[2]/s[0]:.4f})", flush=True)

np.save(OUT / "emb_ids.npy", np.array(ids))
np.save(OUT / "emb_types.npy", np.array(types))
np.save(OUT / "emb_dates.npy", np.array(dates))
np.save(OUT / "pca50.npy", Y)
np.save(OUT / "pca_components.npy", V[:, :K].astype(np.float32))
np.save(OUT / "pca_explained.npy", ev[:K])
print("saved PCA artifacts", flush=True)