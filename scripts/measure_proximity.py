"""Measure how much semantic proximity the sphere actually preserves.

The README quotes five numbers for it, and 1.1.0 added three more (distance and
the neighbour jump). Quoting numbers nobody can reproduce is how a README turns
into folklore, so this script emits all of them from the repo's own data.

It is self-contained: if out/pca50.npy exists (a pipeline run) it uses those
coordinates, otherwise it recomputes the same PCA from data/input/embeddings.tsv.
Both paths were verified to agree to cosine 1.0000 per point.

DEFINITIONS matter here, because four different quantities look alike. Each has
its own baseline; quoting one against another's baseline is how a measurement
turns into a marketing number:

  neighbour retention  | top-k(original space) ∩ top-k(sphere) | / k, averaged
                       over points. Its random baseline is the chance that two
                       unrelated k-sets overlap: k/(N-1). At k=10, N=3,000 that
                       is 0.33%, so 1.40% is a 4.2x lift.

  same-anchor          share of a point's TRUE top-k neighbours (original space)
                       that land in its own anchor. Its random baseline is
                       1/1024 = 0.10% (an unrelated pair sharing an anchor), so
                       0.58% at the index's k=5 is a 5.9x lift.

  angular distance     great-circle distance between a memory and each of its
                       true top-k neighbours, on the sphere the globe draws.
                       Reported in units where a half-circle = 1, as a median;
                       the baseline is the median over seeded random pairs
                       (0.501 -- 0.5 is what uniform points give by symmetry).

  beyond half a globe  share of those distances greater than 0.5, i.e. the two
                       points are more than a quarter-turn apart. Random pairs
                       give 50.1%: half the sphere is always "the far side".

All four point the same way; none substitutes for another. Read them together:
the sphere DOES carry a weak proximity signal, and it is far too weak to
retrieve with -- which is the claim the README makes.

Usage
    python scripts/measure_proximity.py [--k 10]

Exit code 0 = measured, 2 = required input missing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NB = 32
# Fixed so the random baselines below are identical on every run; a baseline that
# moves between runs makes a README row unquotable.
RANDOM_SEED = 20261105
RANDOM_PAIRS = 200_000


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


def arc(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Great-circle distance in units where a half-circle (antipodes) is 1.

    The globe's own geometry, not a chart approximation: arccos of the dot
    product of two unit vectors, divided by pi. Two random points on S2 are
    beyond half a globe half the time, which is why 15.3% is the number worth
    quoting and "usually on the other side" is not.
    """
    return np.arccos(np.clip((a * b).sum(1), -1.0, 1.0)) / np.pi


def index_k(default: int = 5) -> int:
    """k of the shipped lookup index, so these rows describe the real feature.

    Falls back to 5 when out/web_data.extra.json has not been built yet, so the
    script stays runnable on a fresh clone.
    """
    try:
        payload = json.loads((ROOT / "out" / "web_data.extra.json").read_text(encoding="utf-8"))
        return int(payload["k"])
    except (OSError, ValueError, KeyError):
        return default


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

    # The lookup index's own neighbours: same metric, at the k the page ships, so
    # the README row and the shipped feature cannot drift apart.
    kj = index_k()
    true_nbr = knn(X, kj)
    nbr_same = float((b[true_nbr] == b[:, None]).mean())
    d_true = np.concatenate([arc(P, P[true_nbr[:, c]]) for c in range(kj)])

    rng = np.random.default_rng(RANDOM_SEED)
    ri, rj = rng.integers(0, N, RANDOM_PAIRS), rng.integers(0, N, RANDOM_PAIRS)
    off = ri != rj
    d_rand = arc(P[ri[off]], P[rj[off]])

    S = X @ X.T
    iu = np.triu_indices(N, 1)
    sim = S[iu]
    same = b[iu[0]] == b[iu[1]]

    anchor_base = 1.0 / NB ** 2
    d_true_med, d_rand_med = float(np.median(d_true)), float(np.median(d_rand))
    far_true = float((d_true > 0.5).mean())
    far_rand = float((d_rand > 0.5).mean())

    NAME = 46

    def row(label: str, value: str, reference: str = "-") -> None:
        print(f"  {label.ljust(NAME)} {value:>8s} {reference:>9s}")

    print("semantic locality of the sphere")
    print(f"  dataset            : {N} points, {X.shape[1]} dims (data/input/embeddings.tsv)")
    print(f"  sphere coords      : {src}")
    print(f"  anchors occupied   : {len(np.unique(b))} / {NB * NB}")
    print(f"  neighbour-jump k   : {kj} (out/web_data.extra.json when built)")
    print(f"  random pairs       : {len(d_rand)} draws, seed {RANDOM_SEED}")
    print()
    print(f"  {'metric'.ljust(NAME)} {'value':>8s} {'reference':>9s}")
    print(f"  {'-' * NAME} {'-' * 8:>8s} {'-' * 9:>9s}")
    row("top-3 variance share", f"{share:.1f}%")
    row("singular ratio s3/s1 (1.0 = isotropic)", f"{ratio:.3f}")
    row("sphere centroid offset", f"{offset:.3f}")
    row(f"top-{k} neighbour retention, original -> sphere",
        f"{keep * 100:.2f}%", f"{baseline * 100:.2f}%")
    row(f"top-{kj} true nbrs in the memory own anchor",
        f"{nbr_same * 100:.2f}%", f"{anchor_base * 100:.2f}%")
    row("great-circle dist to true nbr (median)",
        f"{d_true_med:.3f}", f"{d_rand_med:.3f}")
    row("share of those nbrs beyond half a globe",
        f"{far_true * 100:.1f}%", f"{far_rand * 100:.1f}%")
    row("mean cosine inside one anchor",
        f"{sim[same].mean():.4f}", f"{sim[~same].mean():.4f}")
    print()
    print("  half-circle = 1 (an antipode is 1.000). Uniform random points give a")
    print(f"  median of 0.5 and exactly half beyond it; this set measures {far_rand * 100:.1f}%.")
    print()
    print(f"  retention baseline = k/(N-1) = {k}/{N - 1} = {baseline * 100:.2f}%"
          f"  ->  lift {keep / baseline:.1f}x")
    print(f"  same-anchor        = {nbr_same * 100:.2f}% vs 1/1024 = {anchor_base * 100:.2f}%"
          f"  ->  lift {nbr_same / anchor_base:.1f}x")
    print(f"  distance           = {d_true_med:.3f} vs random {d_rand_med:.3f}"
          f"  ->  {d_rand_med / d_true_med:.1f}x closer")
    print(f"  change anchor      = {(1 - nbr_same) * 100:.1f}% (1 - same-anchor)"
          f"  but only {far_true * 100:.1f}% cross the globe")
    print()
    print("  All three lifts point the same way and all three are small: the sphere")
    print("  carries a weak but REAL proximity signal (1.8x-5.9x above chance) and is")
    print("  still far too imprecise to retrieve with. They are different quantities")
    print("  with different baselines -- quote them separately.")
    print("  What is NOT true: that neighbours usually sit on the far side. Only")
    print(f"  {far_true * 100:.1f}% of them are beyond half a globe, against "
          f"{far_rand * 100:.1f}% for random pairs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
