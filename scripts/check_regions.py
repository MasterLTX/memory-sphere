"""Gate for named regions: honesty of the labels, and the longitude wrap.

Three things can go wrong with "name this mountain", and each is checked here:

1. A label that is not actually concentrated in its region. Every region must
   carry more of its label than a size-matched random draw, otherwise the label
   is decoration and the region should fall back to a coordinate name.
2. The longitude seam. A mountain sitting on the antimeridian is ONE region; if
   the flood fill forgets that column 31 touches column 0 it silently becomes
   two, and two half-labels read as two facts.
3. Nothing named at all -- a build that quietly degrades to coordinates
   everywhere is not a failure of the code but it is worth seeing.

Usage
    python scripts/check_regions.py [--regions out/regions.json]

Exit code 0 = the labels are earned, 1 = a label or the wrap is wrong, 2 = input missing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NB = 32
THEMES = {"deploy", "storage", "auth", "render", "ops", "docs"}
MIN_LIFT = 1.15


def check_wrap() -> list[str]:
    """A ridge spanning the antimeridian must come back as one component."""
    sys.path.insert(0, str(ROOT / "sphere" / "pipeline"))
    from build_regions import components            # noqa: E402

    mask = np.zeros((NB, NB), dtype=bool)
    mask[10:13, 0] = True          # column 0
    mask[10:13, NB - 1] = True     # column 31 -- adjacent across the seam
    got = components(mask)
    if len(got) != 1:
        return [f"longitude wrap broken: a ridge across the seam split into {len(got)} pieces"]
    if sorted(got[0]) != sorted([(i, j) for i in range(10, 13) for j in (0, NB - 1)]):
        return ["longitude wrap joined the wrong cells"]
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", default=ROOT / "out" / "regions.json", type=Path)
    a = ap.parse_args(argv)

    if not a.regions.exists():
        print(f"missing {a.regions}; run sphere/pipeline/build_regions.py first", file=sys.stderr)
        return 2
    payload = json.loads(a.regions.read_text(encoding="utf-8"))
    regions = payload["regions"]

    problems = []
    named = [r for r in regions if r["source"] != "coord"]
    print(f"{a.regions}")
    print(f"  regions        : {len(regions)}"
          f"  ({sum(1 for r in regions if r['kind'] == 'ridge')} ridges,"
          f" {sum(1 for r in regions if r['kind'] == 'trench')} trenches)")
    print(f"  named w/ data  : {len(named)}   coord fallback: {len(regions) - len(named)}")
    print(f"  memories in named regions: {sum(r['mem'] for r in regions)}")
    print()

    # 1. every data-derived label must be earned
    weak = [r for r in regions
            if r["source"] != "coord" and r["purity"] <= r["baseline"]]
    if weak:
        for r in weak[:5]:
            problems.append(
                f"{r['kind']} '{r['label']}': purity {r['purity']} does not beat "
                f"baseline {r['baseline']}")
    below = [r for r in regions
             if r["source"] != "coord" and r["lift"] < MIN_LIFT]
    if below:
        for r in below[:5]:
            problems.append(
                f"{r['kind']} '{r['label']}': lift {r['lift']} below {MIN_LIFT}, "
                f"label too weak to print")

    # 2. the wrap
    problems += check_wrap()

    # 3. is anything actually being named?
    hits = {r["label"] for r in named} & THEMES
    if len(hits) < 3:
        problems.append(f"only {len(hits)} distinct theme labels ({sorted(hits)});"
                        f" the demo carries 6, so a run this thin suggests a broken join")

    print(f"  distinct labels: {sorted({r['label'] for r in named})}")
    print(f"  themes matched : {sorted(hits)}  ({len(hits)}/6)")
    print(f"  mean lift      : {np.mean([r['lift'] for r in named]):.2f}x"
          if named else "  mean lift      : n/a")
    print()
    if problems:
        for p in problems:
            print(f"  FAIL  {p}")
        print("\nFAIL  region labels are not earned by their own data")
        return 1
    print("PASS  every label beats its size-matched baseline, and the seam is one region")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())