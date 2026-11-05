# -*- coding: utf-8 -*-
"""Find the ridges and trenches on the 32x32 height field and name them.

Why regions and not single anchors: an anchor holds a median of 4 memories, too
few for any label to mean anything. A connected region aggregates 20-50 of them,
which is the smallest unit where a dominant term is worth printing.

Naming is deliberately framed as a STATISTIC, never as an assertion -- see the
`purity` / `baseline` / `lift` fields. v1.0.1 established in the README that a
sphere position barely carries semantic proximity, and a label like "the auth
mountain" would quietly contradict that. The label is therefore always rendered
as `auth * 66% (random 45%)`, never bare.

Sources, in order of trustworthiness, with the one actually used recorded:
    text   highest-frequency content word inside the region  (needs texts.tsv)
    type   dominant memory type (world / experience / observation)
    coord  fallback: the region's centroid, e.g. "ridge at 34N 118E"

The grid wraps in longitude: column 31 is adjacent to column 0. Forgetting that
splits a mountain sitting on the antimeridian into two, which is the classic
spherical-grid bug and is covered by a test.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
from pathlib import Path

import numpy as np

NB = 32
OUT = Path(os.environ.get("SPHERE_OUT", Path(__file__).resolve().parents[2] / "out"))
INP = Path(os.environ.get("SPHERE_INPUT", Path(__file__).resolve().parents[2] / "data" / "input"))

RIDGE_PCT = 85
TRENCH_PCT = 15
MIN_CELLS = 3

STOP = set("""a an the and or of to in on at for with when is are was were be been
being it its this that these those as by from into per environment configured
note interacts""".split())


def wrap_neighbours(i: int, j: int):
    """4-connected neighbours on a lat/lon grid that wraps in longitude."""
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ni, nj = i + di, (j + dj) % NB
        if 0 <= ni < NB:
            yield ni, nj


def components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for i in range(NB):
        for j in range(NB):
            if not mask[i, j] or seen[i, j]:
                continue
            stack = [(i, j)]
            seen[i, j] = True
            cells = []
            while stack:
                ci, cj = stack.pop()
                cells.append((ci, cj))
                for ni, nj in wrap_neighbours(ci, cj):
                    if mask[ni, nj] and not seen[ni, nj]:
                        seen[ni, nj] = True
                        stack.append((ni, nj))
            out.append(cells)
    return out


def cell_of(bin_index: int) -> tuple[int, int]:
    return divmod(int(bin_index), NB)


def tokens(text: str) -> list[str]:
    """ASCII words plus CJK 2-grams, stop-words removed."""
    low = text.lower()
    words = [w for w in re.findall(r"[a-z][a-z\-]{2,}", low) if w not in STOP]
    cjk = re.findall(r"[\u4e00-\u9fff]+", text)
    grams = [c[k:k + 2] for c in cjk for k in range(len(c) - 1)]
    return words + grams


def load_texts() -> dict[str, str]:
    p = INP / "texts.tsv"
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        q = line.split("\t")
        if len(q) >= 2:
            out[q[0]] = q[1]
    return out


def dominant(counter: collections.Counter) -> tuple[str | None, float]:
    if not counter:
        return None, 0.0
    total = sum(counter.values())
    label, n = counter.most_common(1)[0]
    return label, n / max(total, 1)


def coord_label(lat: float, lon: float, kind: str) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{'ridge' if kind == 'ridge' else 'trench'} at {abs(lat):.0f}{ns} {abs(lon):.0f}{ew}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=OUT / "regions.json", type=Path)
    a = ap.parse_args(argv)

    H = np.load(OUT / "height32.npy")
    bin_id = np.load(OUT / "bin_id.npy")
    ids = np.load(OUT / "emb_ids.npy", allow_pickle=True)
    types = np.load(OUT / "emb_types.npy", allow_pickle=True).astype(str)
    texts = load_texts()

    hi_thr = float(np.percentile(H, RIDGE_PCT))
    lo_thr = float(np.percentile(H, TRENCH_PCT))

    # cell -> memory indices
    per_cell: list[list[int]] = [[] for _ in range(NB * NB)]
    for m, b in enumerate(bin_id):
        per_cell[int(b)].append(m)

    rng = np.random.default_rng(0)
    regions = []
    for kind, mask in (("ridge", H >= hi_thr), ("trench", H <= lo_thr)):
        for cells in components(mask):
            if len(cells) < MIN_CELLS:
                continue
            mem = [m for (ci, cj) in cells for m in per_cell[ci * NB + cj]]
            if not mem:
                continue
            vals = np.array([H[ci, cj] for (ci, cj) in cells])
            lat = float(np.degrees(np.arcsin(np.clip(np.mean([np.sin(np.radians(
                (ci + 0.5) / NB * 180 - 90)) for (ci, cj) in cells]), -1, 1))))
            lon = float(np.degrees(np.arctan2(
                np.mean([np.sin(np.radians((cj + 0.5) / NB * 360 - 180)) for (ci, cj) in cells]),
                np.mean([np.cos(np.radians((cj + 0.5) / NB * 360 - 180)) for (ci, cj) in cells]))))

            # --- candidate labels.
            # purity is reported as the share of MEMORIES that carry the label,
            # not the share of tokens: "auth - 62% of these memories mention it"
            # is a sentence a reader can check, "0.143" is not.
            per_mem_tokens = [collections.Counter(tokens(texts.get(str(ids[m]), "")))
                              for m in mem] if texts else []
            cand = {}
            if per_mem_tokens:
                wc = collections.Counter()
                for c in per_mem_tokens:
                    wc.update(c.keys())          # one vote per memory per token
                label, _ = dominant(wc)
                if label:
                    share = sum(1 for c in per_mem_tokens if label in c) / len(mem)
                    cand["text"] = (label, share)
            tl, tshare = dominant(collections.Counter(types[mem].tolist()))
            if tl:
                cand["type"] = (tl, tshare)

            chosen = None
            for src in ("text", "type"):
                if src not in cand:
                    continue
                label, pur = cand[src]
                base = []
                for _ in range(200):
                    pick = rng.integers(0, len(ids), size=len(mem))
                    if src == "type":
                        base.append(dominant(collections.Counter(types[pick].tolist()))[1])
                    else:
                        p2 = [collections.Counter(tokens(texts.get(str(ids[m]), "")))
                              for m in pick]
                        base.append(sum(1 for c in p2 if label in c) / max(len(p2), 1))
                b = float(np.mean(base))
                if pur > b * 1.15:
                    chosen = (label, src, pur, b)
                    break

            if chosen:
                label, src, pur, base = chosen
            else:
                label, src, pur = coord_label(lat, lon, kind), "coord", 0.0
                base = 0.0

            regions.append({
                "kind": kind,
                "cells": [ci * NB + cj for (ci, cj) in cells],
                "cellsN": len(cells),
                "centroid": [round(lon, 2), round(lat, 2)],
                "peak": round(float(vals.max()), 4),
                "mean": round(float(vals.mean()), 4),
                "mem": len(mem),
                "label": label,
                "source": src,
                "purity": round(float(pur), 3),
                "baseline": round(float(base), 3),
                "lift": round(float(pur / base), 2) if base > 0 else 0.0,
            })

    regions.sort(key=lambda r: -r["mem"])
    payload = {
        "thresholds": {"ridge": round(hi_thr, 4), "trench": round(lo_thr, 4),
                       "ridgePct": RIDGE_PCT, "trenchPct": TRENCH_PCT},
        "regions": regions,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    ridges = [r for r in regions if r["kind"] == "ridge"]
    trenches = [r for r in regions if r["kind"] == "trench"]
    print(f"thresholds  ridge >= {hi_thr:.4f} (p{RIDGE_PCT})   trench <= {lo_thr:.4f} (p{TRENCH_PCT})")
    print(f"regions     {len(ridges)} ridges, {len(trenches)} trenches  "
          f"(>= {MIN_CELLS} cells)")
    print(f"memories    {sum(r['mem'] for r in regions)} of {len(ids)} land in a named region")
    print()
    print(f"  {'kind':7s} {'cells':>5s} {'mem':>5s}  {'label':16s} {'src':5s} {'purity':>6s} {'base':>6s} {'lift':>5s}")
    for r in regions[:12]:
        print(f"  {r['kind']:7s} {r['cellsN']:5d} {r['mem']:5d}  {r['label'][:16]:16s} "
              f"{r['source']:5s} {r['purity']:6.3f} {r['baseline']:6.3f} {r['lift']:5.2f}")
    print()
    by_src = collections.Counter(r["source"] for r in regions)
    print(f"  label sources: {dict(by_src)}")
    print(f"  wrote {a.out}  ({a.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())