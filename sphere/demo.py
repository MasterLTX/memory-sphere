# -*- coding: utf-8 -*-
"""Synthesise a fake memory store so the pipeline can be run without any private data.

Design goals
------------
* reproducible  - one seed produces byte-identical files
* structurally realistic - clustered embeddings, intra-cluster links, three fact
  types with a realistic skew, and a 25-day creation timeline
* contract-faithful - writes exactly the four files described in the README

Nothing in here is derived from anyone's real memories.
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import random
from pathlib import Path

import numpy as np

CLUSTERS = 6
TYPES = [("world", 0.80), ("experience", 0.18), ("observation", 0.02)]

# A small thematic vocabulary so the demo reads like something, not like noise.
THEMES = [
    ("deploy", ["rollout", "canary", "rollback", "artifact", "registry"]),
    ("storage", ["index", "segment", "compaction", "replica", "shard"]),
    ("auth", ["token", "scope", "session", "revoke", "grant"]),
    ("render", ["mesh", "normal", "shader", "lens", "raster"]),
    ("ops", ["alert", "threshold", "runbook", "oncall", "postmortem"]),
    ("docs", ["draft", "outline", "revision", "citation", "glossary"]),
]


def _pick_type(rng: random.Random) -> str:
    r = rng.random()
    acc = 0.0
    for name, p in TYPES:
        acc += p
        if r <= acc:
            return name
    return TYPES[-1][0]


def _fake_text(rng: random.Random, theme: tuple[str, list[str]], idx: int) -> str:
    name, words = theme
    w = rng.sample(words, k=min(3, len(words)))
    return (f"{name.capitalize()} note #{idx}: {w[0]} interacts with {w[1]} when {w[2]} "
            f"is configured per environment.")


def generate(
    out_dir: Path,
    units: int = 3000,
    dims: int = 64,
    links: int = 6000,
    days: int = 25,
    seed: int = 20261105,
) -> dict:
    rng = random.Random(seed)
    nprng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- cluster centres: orthonormal-ish random directions in R^dims
    centres = nprng.normal(size=(CLUSTERS, dims))
    centres /= np.linalg.norm(centres, axis=1, keepdims=True)

    assign = [rng.randrange(CLUSTERS) for _ in range(units)]
    noise = nprng.normal(scale=0.55, size=(units, dims))
    vecs = centres[assign] + noise
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

    start = dt.date(2026, 10, 11)
    dates = [start + dt.timedelta(days=rng.randrange(days)) for _ in range(units)]

    ids = [f"demo-{i:05d}" for i in range(units)]
    types = [_pick_type(rng) for _ in range(units)]

    def fmt_vec(v: np.ndarray) -> str:
        return "[" + ",".join(f"{x:.6f}" for x in v) + "]"

    with open(out_dir / "embeddings.tsv", "w", encoding="utf-8", newline="\n") as f:
        for i in range(units):
            f.write(f"{ids[i]}\t{types[i]}\t{dates[i].isoformat()}\t{fmt_vec(vecs[i])}\n")

    # ---- links: mostly intra-cluster, a few cross-cluster bridges
    by_cluster: dict[int, list[int]] = {}
    for i, c in enumerate(assign):
        by_cluster.setdefault(c, []).append(i)

    edges = set()
    written = 0
    with open(out_dir / "links.tsv", "w", encoding="utf-8", newline="\n") as f:
        attempts = 0
        while written < links and attempts < links * 20:
            attempts += 1
            i = rng.randrange(units)
            if rng.random() < 0.08:                      # bridge
                j = rng.randrange(units)
            else:                                        # same cluster
                mates = by_cluster[assign[i]]
                if len(mates) < 2:
                    continue
                j = mates[rng.randrange(len(mates))]
            if i == j or (i, j) in edges:
                continue
            edges.add((i, j))
            w = round(rng.uniform(0.45, 1.0), 4)
            kind = "entity" if rng.random() < 0.7 else "temporal"
            f.write(f"{ids[i]}\t{ids[j]}\t{w}\t{kind}\n")
            written += 1

    # ---- entity counts: hubs get more entities
    with open(out_dir / "ent_count.tsv", "w", encoding="utf-8", newline="\n") as f:
        for i in range(units):
            k = 0 if rng.random() < 0.12 else rng.randint(1, 9)
            if k:
                f.write(f"{ids[i]}\t{k}\n")

    # ---- model markers (one per cluster, jittered)
    with open(out_dir / "models.tsv", "w", encoding="utf-8", newline="\n") as f:
        for ci, (name, _) in enumerate(THEMES):
            m = centres[ci] + nprng.normal(scale=0.08, size=dims)
            m /= np.linalg.norm(m)
            f.write(f"{name}\t{fmt_vec(m)}\n")

    # ---- optional display texts
    with open(out_dir / "texts.tsv", "w", encoding="utf-8", newline="\n") as f:
        for i in range(units):
            f.write(f"{ids[i]}\t{_fake_text(rng, THEMES[assign[i]], i)}\n")

    return {
        "units": units, "dims": dims, "links": written,
        "clusters": CLUSTERS, "days": days, "seed": seed,
        "out": str(out_dir),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate a synthetic memory store.")
    ap.add_argument("--out", default="data/input", type=Path)
    ap.add_argument("--units", default=3000, type=int)
    ap.add_argument("--dims", default=64, type=int)
    ap.add_argument("--links", default=6000, type=int)
    ap.add_argument("--days", default=25, type=int)
    ap.add_argument("--seed", default=20261105, type=int)
    a = ap.parse_args(argv)
    info = generate(a.out, a.units, a.dims, a.links, a.days, a.seed)
    print(f"demo data -> {info['out']}")
    print(f"  {info['units']} units x {info['dims']} dims · {info['links']} links · "
          f"{info['clusters']} clusters · {info['days']} days · seed={info['seed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())