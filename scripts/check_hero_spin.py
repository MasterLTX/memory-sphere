"""Regression check: does the hero GIF spin about the VERTICAL axis?

The bug this guards against (fixed in 1.0.1): the render matrix was

    M = rmat_x(radians(72)) @ rmat_y(angle)

Rx(t) maps the spin axis y_hat to (0, cos t, sin t). At t=72 deg that is
(0, 0.309, 0.951) -- 95% along +z, i.e. straight down the view axis -- so the
globe rotated *in the image plane* like a plate instead of turning like a
planet. It looked like motion, which is why the first "verification" (a few
still frames side by side) missed it.

This script decides from pixels. Two competing models are fitted to every pair
of consecutive frames inside the globe mask:

    A) in-plane rotation by theta about the image centre  -> plate spin (BAD)
    B) horizontal translation by (dx, dy)                 -> planet spin (GOOD)

Because both models have very different parameter counts, the comparison is
read as a *ratio*, not an absolute: planet spin expects the translation
residual to be clearly lower, and |dy|/|dx| to be near zero (a pure horizontal
slide). The plate spin produced the exact opposite.

Usage
    python scripts/check_hero_spin.py [path/to/rotating.gif]

Exit code 0 = the GIF spins like a planet, 1 = it does not (or is ambiguous).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# A planet spin must beat the plate model by at least this factor, and the
# residual vertical drift must stay under this fraction of the horizontal one.
MIN_TRANSLATION_ADVANTAGE = 0.85
MAX_VERTICAL_FRACTION = 0.25


def load_frames(path: Path, limit: int = 12) -> list[np.ndarray]:
    im = Image.open(path)
    n = getattr(im, "n_frames", 1)
    out = []
    for i in range(min(n, limit)):
        im.seek(i)
        out.append(np.asarray(im.convert("L"), dtype=np.float32))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gif", nargs="?", default="examples/rotating.gif", type=Path)
    ap.add_argument("--limit", default=12, type=int,
                    help="how many consecutive frames to test (default 12)")
    a = ap.parse_args(argv)

    if not a.gif.exists():
        print(f"no such file: {a.gif}", file=sys.stderr)
        return 2

    frames = load_frames(a.gif, a.limit)
    if len(frames) < 3:
        print("need at least 3 frames", file=sys.stderr)
        return 2

    H, W = frames[0].shape
    yy, xx = np.mgrid[0:H, 0:W]
    CY, CX = (H - 1) / 2, (W - 1) / 2
    rad = np.hypot(yy - CY, xx - CX)
    # generous inset: the rim of the disc is the noisiest part of the image
    mask = rad < 0.36 * W

    def sad(a_: np.ndarray, b_: np.ndarray) -> float:
        d = (a_ - b_)[mask]
        return float(np.sqrt(np.mean(d * d)))

    def rotated(a_: np.ndarray, deg: float) -> np.ndarray:
        img = Image.fromarray(a_)
        return np.asarray(img.rotate(deg, resample=Image.BICUBIC, center=(CX, CY)),
                          dtype=np.float32)

    def shifted(a_: np.ndarray, dx: float, dy: float) -> np.ndarray:
        img = Image.fromarray(a_)
        return np.asarray(img.transform((W, H), Image.AFFINE,
                                        (1, 0, -dx, 0, 1, -dy),
                                        resample=Image.BICUBIC), dtype=np.float32)

    n_total = getattr(Image.open(a.gif), "n_frames", len(frames))
    step = 360.0 / n_total
    pairs = list(zip(frames, frames[1:]))

    rot_best, shift_best = [], []
    for a_, b_ in pairs:
        cand = [(sad(rotated(a_, d), b_), d)
                for d in np.arange(-2 * step, 2 * step + 1e-9, step / 2)]
        cand.sort()
        rot_best.append(cand[0])
        cand2 = [(sad(shifted(a_, dx, dy), b_), dx, dy)
                 for dx in range(-24, 25, 3) for dy in range(-12, 13, 3)]
        cand2.sort()
        shift_best.append(cand2[0])

    still = float(np.mean([sad(a_, b_) for a_, b_ in pairs]))
    rot_res = float(np.mean([c[0] for c in rot_best]))
    sft_res = float(np.mean([c[0] for c in shift_best]))
    rot_deg = float(np.mean([c[1] for c in rot_best]))
    dx = float(np.mean([c[1] for c in shift_best]))
    dy = float(np.mean([c[2] for c in shift_best]))
    vert_frac = abs(dy) / max(abs(dx), 1e-6)

    print(f"{a.gif}  frames={n_total}  tested={len(frames)}  size={W}x{H}")
    print()
    print(f"  baseline (no motion)         {still:8.3f}")
    print(f"  model A  in-plane rotation   {rot_res:8.3f}   {rot_deg:+7.2f} deg/frame")
    print(f"  model B  horizontal slide    {sft_res:8.3f}   dx {dx:+7.1f} px  dy {dy:+6.1f} px")
    print()
    print(f"  translation / rotation ratio {sft_res / rot_res:8.3f}"
          f"   (planet spin needs < {MIN_TRANSLATION_ADVANTAGE})")
    print(f"  vertical fraction |dy|/|dx|  {vert_frac:8.3f}"
          f"   (planet spin needs < {MAX_VERTICAL_FRACTION})")

    ok = (sft_res / rot_res < MIN_TRANSLATION_ADVANTAGE) and (vert_frac < MAX_VERTICAL_FRACTION)
    print()
    if ok:
        print("PASS  the globe turns about the vertical axis (planet spin)")
        return 0
    if rot_res < sft_res * MIN_TRANSLATION_ADVANTAGE:
        print("FAIL  the globe rotates in the image plane (plate spin) -- spin axis is")
        print("      pointing down the view axis; check the tilt passed to rmat_x().")
    else:
        print("FAIL  ambiguous: neither a rotation nor a horizontal slide explains"
              " the motion.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())