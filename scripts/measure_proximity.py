"""Measure how much semantic proximity the sphere actually preserves.

The README claims the sphere does NOT preserve semantic neighbours, and quotes
five numbers for it. Quoting numbers nobody can reproduce is how a README turns
into folklore, so this script emits all of them from the repo's own data.

It is self-contained: if out/pca50.npy exists (a pipeline run) it uses those
coordinates, otherwise it recomputes the same PCA from data/input/embeddings.tsv.
Both paths were verified to agree to cosine 1.0000 per point.

DEFINITIONS matter here, because two different quantities look alike:

  neighbour retention  | top10(original space) ∩ top10(sphere) | / 10, averaged
                       over points. Its random baseline is the chance that two
                       unrelated 10-sets overlap: 10/(N-1). At N=3,000 that is
                       0.33%, so 1.40% is a 4.2x lift.

  same-anchor fraction of a point's original top-10 neighbours sharing its own
                       anchor. Its random baseline is 1/1024 = 0.10%, so 0.49%
                       is a 4.9x lift.

Both point the same way; neither substitutes for the other. Do not quote one
against the other's baseline.

Usage
    python scripts/measure_proximity.py [--k 10] [--quiet]

Exit code 0 = measured, 2 = required input missing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NB = 32


def load_raw() -> np.ndarray:
    """The committed input contract: id, type, date, [v1,v2,...]."""
    path = ROOT / "data" / "input" / "embeddings.tsv"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        p = line.split("\t")
        if len(p) < 4:
            continue
        rows.append([float(t) for t in p[3].strip().strip("[]").split(",") if t.strip()])
    return np.asarray(rows)


def centred_l2(X: np.ndarray) -> np.ndarray:
    X = X - X.mean(0)
    return X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)


def sphere_coords() -> tuple[np.ndarray, str]:
    """Either the pipeline's own PCA50 or an equivalent recompute."""
    pca = ROOT / "out" / "pca50.npy"
    if pca.exists():
        Y = np.load(pca)
        src = "out/pca50.npy (pipeline output)"
    else:
        X = centred_l2(load_raw())
        w, V = np.linalg.eigh(X.T @ X / len(X))
        Y = X @ V[:, np.argsort(w)[::-1]]
        src = "recomputed from data/input/embeddings.tsv"
    Y3 = Y[:, :3].astype(np.float64)
    Y3 -= Y3.mean(0)
    P = Y3 / np.maximum(np.linalg.norm(Y3, axis=1, keepdims=True), 1e-12)
    return P, src


def anchors(P: np.ndarray) -> np.ndarray:
    """32x32 equal-area bins, exactly as build_sphere.py lines 34-38."""
    z = P[:, 2]
    lam = np.arctan2(P[:, 1], P[:, 0])
    bi = np.clip(((z + 1) / 2 * NB).astype(int), 0, NB - 1)
    bj = np.clip(((lam + np.pi) / (2 * np.pi) * NB).astype(int), 0, NB - 1)
    return bi * NB + bj


def knn(A: np.ndarray, k: int) -> np.ndarray:
    S = A @ A.T
    np.fill_diagonal(S, -2.0)
    return np.argsort(-S, axis=1)[:, :k]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", default=10, type=int, help="neighbour count (default 10)")
    a = ap.parse_args(argv)

    if not (ROOT / "data" / "input" / "embeddings.tsv").exists():
        print(f"missing {ROOT / 'data' / 'input' / 'embeddings.tsv'}; run "
              f"`python -m sphere demo` first to synthesise one", file=sys.stderr)
        return 2

    X = centred_l2(load_raw())
    P, src = sphere_coords()
    b = anchors(P)
    N = len(X)
    k = a.k

    w, _ = np.linalg.eigh(X.T @ X / N)
    w = np.sort(w)[::-1]
    share = float(w[:3].sum() / w.sum() * 100)
    ratio = float(np.sqrt(w[2]) / np.sqrt(w[0]))
    offset = float(np.linalg.norm(P.mean(0)))

    hi, lo = knn(X, k), knn(P, k)
    keep = float(np.mean([len(set(i) & set(j)) / k for i, j in zip(hi, lo)]))
    baseline = k / (N - 1)

    same_anchor = float(np.mean([(b[hi[i]] == b[i]).sum() / k for i in range(N)]))

    S = X @ X.T
    iu = np.triu_indices(N, 1)
    sim = S[iu]
    same = b[iu[0]] == b[iu[1]]

    print("semantic locality of the sphere")
    print(f"  dataset            : {N} points, {X.shape[1]} dims (data/input/embeddings.tsv)")
    print(f"  sphere coords      : {src}")
    print(f"  anchors occupied   : {len(np.unique(b))} / {NB * NB}")
    print()
    print(f"  {'metric':46s} {'value':>8s} {'baseline':>9s}")
    print(f"  {'-' * 46} {'-' * 8:>8s} {'-' * 9:>9s}")
    print(f"  {'top-3 variance share':46s} {share:7.1f}% {'-':>9s}")
    print(f"  {'singular ratio s3/s1 (1.0 = isotropic)':46s} {ratio:8.3f} {'-':>9s}")
    print(f"  {'sphere centroid offset':46s} {offset:8.3f} {'-':>9s}")
    print(f"  {f'top-{k} neighbour retention, original -> sphere':46s} "
          f"{keep * 100:7.2f}% {baseline * 100:8.2f}%")
    print(f"  {f'mean cosine inside one anchor':46s} "
          f"{sim[same].mean():8.4f} {sim[~same].mean():9.4f}")
    print()
    print(f"  retention baseline = k/(N-1) = {k}/{N - 1} = {baseline * 100:.2f}%"
          f"  ->  lift {keep / baseline:.1f}x")
    print(f"  same-anchor count  = {same_anchor * 100:.2f}%"
          f"   random baseline 1/1024 = {100 / NB ** 2:.2f}%  ->  lift "
          f"{same_anchor / (1.0 / NB ** 2):.1f}x")
    print()
    print("  Both metrics say the same thing: the sphere keeps a few percent of the")
    print("  original neighbourhoods, far too little to retrieve with. They are")
    print("  different quantities with different baselines -- quote them separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
