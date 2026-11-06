# -*- coding: utf-8 -*-
"""Build the CLOUD field: how far each cell's memories reach for their neighbours.

The cloud is deliberately NOT a duplicate of the land. Two candidate definitions
were measured against the existing height field:

    link count  (cross-anchor edges per cell)   spearman vs count  +0.998  -> discard
    link reach  (mean great-circle arc to the    spearman vs count  -0.264
                 memory's own top-k neighbours)  spearman vs height +0.018  -> keep

So "cloud thickness" means: the memories gathered here have their real
neighbours somewhere far away. A thick cloud marks isolation, not density.

Raw reach is speckle (neighbour disagreement 0.133); it needs two things to read
as cloud at all: a gaussian smooth in both directions (longitude wraps), and a
contrast stretch. Both are applied here so the page does not have to.

Two scales are exported, because clouds read better as big masses plus small
puffs than as one blur:

    big    sigma 2.5   large drifting masses
    small  sigma 0.6   the puffs that make the mass feel volumetric

Output: out/cloud32.npz  with fields normalised to 0..1 over occupied cells.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

NB = 32
OUT = Path(os.environ.get("SPHERE_OUT", Path(__file__).resolve().parents[2] / "out"))
INP = Path(os.environ.get("SPHERE_INPUT", Path(__file__).resolve().parents[2] / "data" / "input"))
K = 5


def load_vectors() -> np.ndarray:
    rows = []
    for line in (INP / "embeddings.tsv").read_text(encoding="utf-8").splitlines():
        p = line.split("\t")
        if len(p) < 4:
            continue
        rows.append([float(t) for t in p[3].strip().strip("[]").split(",") if t.strip()])
    X = np.asarray(rows)
    X = X - X.mean(0)
    return X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)


def cell_dir(b: int) -> np.ndarray:
    i, j = divmod(int(b), NB)
    z = (i + 0.5) / NB * 2 - 1
    lam = (j + 0.5) / NB * 2 * np.pi - np.pi
    r = np.sqrt(max(1 - z * z, 0))
    return np.array([r * np.cos(lam), r * np.sin(lam), z])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=OUT / "cloud32.npz", type=Path)
    a = ap.parse_args(argv)

    X = load_vectors()
    n = len(X)

    # sphere coordinates must be the SAME ones the bins were built from
    pca = OUT / "pca50.npy"
    if pca.exists():
        Y = np.load(pca)[:, :3].astype(np.float64)
        src = "out/pca50.npy"
    else:
        w, V = np.linalg.eigh(X.T @ X / n)
        Y = X @ V[:, np.argsort(w)[::-1]][:, :3]
        src = "recomputed"
    Y = Y - Y.mean(0)
    P = Y / np.maximum(np.linalg.norm(Y, axis=1, keepdims=True), 1e-12)

    bi = np.clip((((P[:, 2] + 1) / 2) * NB).astype(int), 0, NB - 1)
    bj = np.clip(((np.arctan2(P[:, 1], P[:, 0]) + np.pi) / (2 * np.pi) * NB).astype(int), 0, NB - 1)
    cell = bi * NB + bj
    occ = np.bincount(cell, minlength=NB * NB) > 0

    # blocked: a full 10.8k x 10.8k cosine matrix would be ~931 MB
    def topk_blockwise(block: int = 1024) -> np.ndarray:
        out = np.zeros((n, K), dtype=np.int64)
        for s in range(0, n, block):
            e = min(s + block, n)
            S = X[s:e] @ X.T
            for r in range(e - s):
                S[r, s + r] = -2.0
            idx = np.argpartition(-S, kth=K, axis=1)[:, :K]
            rows = np.arange(e - s)[:, None]
            out[s:e] = idx[rows, np.argsort(-S[rows, idx], axis=1)]
        return out

    nb = topk_blockwise()

    D = np.array([cell_dir(b) for b in range(NB * NB)])
    arc = np.arccos(np.clip(np.sum(D[cell[:, None]] * D[cell[nb]], axis=2), -1, 1)) / np.pi
    cross = cell[nb] != cell[:, None]

    tot = np.zeros(NB * NB)
    den = np.zeros(NB * NB)
    np.add.at(tot, cell, (arc * cross).sum(1))
    np.add.at(den, cell, cross.sum(1))
    reach = np.where(den > 0, tot / np.maximum(den, 1e-9), np.nan).reshape(NB, NB)

    occ2 = occ.reshape(NB, NB)
    fill = np.nanmean(reach)
    filled = np.where(occ2 & ~np.isnan(reach), reach, fill)

    def norm(F, keep_mask):
        v = F[keep_mask]
        lo, hi = v.mean() - 2 * v.std(), v.mean() + 2 * v.std()
        return np.clip((F - lo) / max(hi - lo, 1e-9), 0.0, 1.0)

    big = norm(gaussian_filter(filled, (2.5, 2.5), mode=("nearest", "wrap")), occ2)
    small = norm(gaussian_filter(filled, (0.6, 0.6), mode=("nearest", "wrap")), occ2)

    # keep unoccupied cells exactly zero so the page draws no cloud there
    big = np.where(occ2, big, 0.0)
    small = np.where(occ2, small, 0.0)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out, big=big.astype(np.float32), small=small.astype(np.float32),
                        occupied=occ2.astype(np.uint8))

    from scipy.stats import spearmanr
    H = np.load(OUT / "height32.npy")
    cnt = np.load(OUT / "count32.npy")
    print(f"cloud field from {src}, {n} memories, k={K}")
    print(f"  reach raw  : median {np.nanmedian(reach):.3f}  max {np.nanmax(reach):.3f}")
    print(f"  big   sigma 2.5 : std {big[occ2].std():.3f}  range {big[occ2].min():.2f}..{big[occ2].max():.2f}")
    print(f"  small sigma 0.6 : std {small[occ2].std():.3f}  range {small[occ2].min():.2f}..{small[occ2].max():.2f}")
    print(f"  vs height  : spearman {spearmanr(big[occ2], H[occ2]).statistic:+.3f}"
          f"   (near 0 = independent of the terrain)")
    print(f"  vs count   : spearman {spearmanr(big[occ2], cnt[occ2]).statistic:+.3f}")
    print(f"  wrote {a.out} ({a.out.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())