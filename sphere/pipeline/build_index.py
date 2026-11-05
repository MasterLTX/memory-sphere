# -*- coding: utf-8 -*-
"""Export the lookup index the interactive page needs: who is where, and who is near whom.

Two different notions of "near" live here on purpose:

  idbin   each memory's anchor on the sphere      -> answers "where is this one"
  knn     each memory's true top-k in the ORIGINAL vector space -> answers
          "what is actually like this one", which the sphere cannot answer
          (v1.0.1 measured only 1.40% neighbour retention on the sphere).

Keeping both in one file makes the contrast inspectable: a memory's true
neighbours routinely sit on the other side of the globe.

The neighbour search is blocked so an 10k x 10k cosine matrix never materialises
(that would be ~872 MB); each block keeps only its top-k.

Output: out/web_data.extra.json  (loaded on demand, not embedded in the page)
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("SPHERE_OUT", Path(__file__).resolve().parents[2] / "out"))
INP = Path(os.environ.get("SPHERE_INPUT", Path(__file__).resolve().parents[2] / "data" / "input"))


def load_raw() -> np.ndarray:
    rows = []
    for line in (INP / "embeddings.tsv").read_text(encoding="utf-8").splitlines():
        p = line.split("\t")
        if len(p) < 4:
            continue
        rows.append([float(t) for t in p[3].strip().strip("[]").split(",") if t.strip()])
    X = np.asarray(rows, dtype=np.float64)
    X = X - X.mean(0)
    return X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)


def topk_blockwise(X: np.ndarray, k: int, block: int = 1024) -> np.ndarray:
    N = len(X)
    out = np.zeros((N, k), dtype=np.int64)
    for s in range(0, N, block):
        e = min(s + block, N)
        S = X[s:e] @ X.T                      # (block, N) -- bounded memory
        for r in range(e - s):
            S[r, s + r] = -2.0                # exclude self
        idx = np.argpartition(-S, kth=k, axis=1)[:, :k]
        rows = np.arange(e - s)[:, None]
        order = np.argsort(-S[rows, idx], axis=1)
        out[s:e] = idx[rows, order]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", default=5, type=int)
    ap.add_argument("--out", default=OUT / "web_data.extra.json", type=Path)
    a = ap.parse_args(argv)

    ids = np.load(OUT / "emb_ids.npy", allow_pickle=True).astype(str)
    bin_id = np.load(OUT / "bin_id.npy").astype(np.int64)
    X = load_raw()
    if len(X) != len(ids):
        print(f"vector count {len(X)} != id count {len(ids)}", flush=True)
        return 2

    knn = topk_blockwise(X, a.k)
    # how often does a true neighbour sit in a different anchor? that is the
    # whole point of exposing the jump
    cross = float(np.mean(bin_id[knn] != bin_id[:, None]))

    payload = {
        "k": a.k,
        "n": len(ids),
        "ids": list(ids),
        "idbin": base64.b64encode(bin_id.astype(np.uint16).tobytes()).decode(),
        "knn": base64.b64encode(knn.astype(np.uint16).tobytes()).decode(),
        "crossAnchor": round(cross, 4),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    print(f"memories         : {len(ids)}")
    print(f"true top-{a.k} neighbours computed in the original space")
    print(f"  cross-anchor rate : {cross:.3f}   "
          f"(share of true neighbours that land in a different anchor)")
    print(f"wrote {a.out}  ({a.out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())