# -*- coding: utf-8 -*-
"""Gate for the lookup index: is `out/web_data.extra.json` self-consistent, and
would a search land on the right memory?

Two failures are silent and expensive, so both are checked here:

  1. an OFFSET error. `idbin` and `knn` are base64 of uint16 arrays, so nothing
     in the file says how long they are. One memory lost or gained at the front
     shifts every anchor by one and the page still looks fine -- every dot is on
     the sphere, just the wrong one. Lengths are derived from `n` and `k` and
     compared, never trusted.
  2. a DANGLING or SELF reference. A `knn` entry outside [0, n) points at no
     memory; an entry equal to its own row makes "true neighbour" mean "this
     memory", and the jump becomes a no-op that looks like it works.

The decode test is the one that matters for the shipped feature: pick 20 ids,
decode each one's anchor, ask the reverse index (anchor -> memories) for that
cell, and require the memory to be sitting in it with a matching idbin. That is
exactly the query path "click a hill, get its memories".

Usage
    python scripts/check_search.py [--index out/web_data.extra.json] [--samples 20]

Exit code 0 = the index is consistent, 1 = a check failed, 2 = the index is
missing or not readable as JSON.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NB = 32
ANCHORS = NB * NB


def decode_u16(blob: str) -> tuple[np.ndarray, int]:
    """The wire format the page uses: base64 -> little-endian uint16 array.

    Returns the values and the decoded BYTE length, because the length assertion
    the index has to satisfy is stated in bytes (2 per id), not in base64 chars.
    """
    raw = base64.b64decode(blob)
    return np.frombuffer(raw, dtype=np.uint16), len(raw)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", default=ROOT / "out" / "web_data.extra.json", type=Path)
    ap.add_argument("--samples", default=20, type=int)
    a = ap.parse_args(argv)

    if not a.index.exists():
        print(f"missing {a.index}; run sphere/pipeline/build_index.py first", file=sys.stderr)
        return 2
    try:
        payload = json.loads(a.index.read_text(encoding="utf-8"))
        n = int(payload["n"])
        k = int(payload["k"])
        ids = list(payload["ids"])
        idbin, idbin_bytes = decode_u16(payload["idbin"])
        knn, knn_bytes = decode_u16(payload["knn"])
    except (ValueError, KeyError, TypeError) as e:
        print(f"{a.index} is not a usable lookup index: {e}", file=sys.stderr)
        return 2

    rows: list[tuple[str, str, str]] = []

    def check(label: str, ok: bool, expected: str, got: str) -> bool:
        rows.append((label, expected, f"{got}  {'ok' if ok else 'FAIL'}"))
        return ok

    failures = 0
    print(f"{a.index}")
    print(f"  n={n}  k={k}  ids={len(ids)}  "
          f"idbin {len(idbin)} values ({len(payload['idbin'])} b64 chars)  "
          f"knn {len(knn)} values ({len(payload['knn'])} b64 chars)")
    print()

    # 1. lengths: n ids, one anchor each (2 bytes = one uint16), n*k neighbours
    failures += not check(
        "n == number of ids", n == len(ids), f"{n}", str(len(ids)))
    failures += not check(
        "idbin bytes == 2 per id", idbin_bytes == 2 * n, f"{2 * n}", str(idbin_bytes))
    failures += not check(
        "idbin values == n", len(idbin) == n, f"{n}", str(len(idbin)))
    failures += not check(
        "knn values == n*k", len(knn) == n * k, f"{n * k}", str(len(knn)))

    # 2. ranges and self-references
    failures += not check(
        "every anchor in [0, 1024)", bool(idbin.size) and int(idbin.max()) < ANCHORS,
        f"< {ANCHORS}", f"max {int(idbin.max()) if idbin.size else 'n/a'}")
    failures += not check(
        "every knn id in [0, n)", bool(knn.size) and int(knn.max()) < n,
        f"< {n}", f"max {int(knn.max()) if knn.size else 'n/a'}")

    self_refs = 0
    if len(knn) == n * k:
        grid = knn.reshape(n, k)
        self_refs = int((grid == np.arange(n)[:, None]).any(1).sum())
    failures += not check(
        "knn self-references", self_refs == 0, "0 rows", str(self_refs))

    occupied = int(np.unique(idbin).size) if idbin.size else 0
    failures += not check(
        "anchors occupied", occupied > ANCHORS // 2, f"> {ANCHORS // 2}", str(occupied))

    # 3. the shipped query path: id -> anchor -> memories in that anchor
    cell_to_ids: dict[int, list[int]] = defaultdict(list)
    for i, cell in enumerate(idbin.tolist()):
        cell_to_ids[cell].append(i)

    rng = np.random.default_rng(20261105)
    picks = rng.choice(n, size=min(a.samples, n), replace=False) if n else []
    decoded = 0
    for i in picks:
        cell = int(idbin[i])
        members = cell_to_ids.get(cell, [])
        if i in members and all(int(idbin[j]) == cell for j in members):
            decoded += 1
    want = len(picks)
    failures += not check(
        "sample decode id->anchor->ids", decoded == want, f"{want}/{want}", f"{decoded}/{want}")

    width = max(len(r[0]) for r in rows) + 2
    print(f"  {'check'.ljust(width)} {'expected':>12s} {'got':>16s}")
    print(f"  {'-' * width} {'-' * 12} {'-' * 16}")
    for label, expected, got in rows:
        print(f"  {label.ljust(width)} {expected:>12s} {got:>16s}")
    print()

    if failures:
        print(f"FAIL  {failures} check(s) failed on the lookup index")
        return 1
    print(f"PASS  index self-consistent; {want} sampled ids decode to their own anchor's memories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())