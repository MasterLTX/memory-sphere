# -*- coding: utf-8 -*-
"""Render a rotating GIF of the globe (for the README hero)."""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

NB = 32


def icosphere(subdiv=4):
    t = (1 + math.sqrt(5)) / 2
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
         (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4),
         (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8),
         (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    V = [np.array(v, float) / np.linalg.norm(v) for v in V]
    for _ in range(subdiv):
        cache, newF = {}, []

        def mid(a, b):
            k = (a, b) if a < b else (b, a)
            if k in cache:
                return cache[k]
            m = V[a] + V[b]
            m /= np.linalg.norm(m)
            V.append(m)
            cache[k] = len(V) - 1
            return cache[k]

        for a, b, c in F:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            newF += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        F = newF
    return np.array(V), np.array(F, np.int64)


STOPS = np.array([[0.015, 0.030, 0.095], [0.030, 0.105, 0.270], [0.040, 0.230, 0.415],
                  [0.060, 0.395, 0.435], [0.180, 0.560, 0.365], [0.510, 0.660, 0.290],
                  [0.860, 0.715, 0.320], [1.000, 0.935, 0.770]])
TINT = np.array([[0.28, 0.52, 1.00], [0.34, 0.95, 0.58], [1.00, 0.40, 0.32]])
LIGHT = np.array([-0.40, 0.58, 0.71]); LIGHT /= np.linalg.norm(LIGHT)
HALF = LIGHT + np.array([0, 0, 1.0]); HALF /= np.linalg.norm(HALF)
LIGHT2 = np.array([0.55, -0.62, 0.30]); LIGHT2 /= np.linalg.norm(LIGHT2)


def palette(h):
    x = np.clip(h, 0, 1) * (len(STOPS) - 1)
    i = np.clip(np.floor(x).astype(int), 0, len(STOPS) - 2)
    f = (x - i)[..., None]
    return STOPS[i] * (1 - f) + STOPS[i + 1] * f


def rmat_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rmat_z(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rmat_y(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def build():
    Hs = np.load(Path(os.environ.get("SPHERE_OUT", "out")) / "height32.npy")
    tf = np.load(Path(os.environ.get("SPHERE_OUT", "out")) / "typefrac32.npy").reshape(3, NB, NB)
    Vd, F = icosphere(4)
    x, y, z = Vd[:, 0], Vd[:, 1], Vd[:, 2]
    th = np.arcsin(np.clip(z, -1, 1)); ph = np.arctan2(y, x)
    fi = (th + np.pi / 2) / np.pi * NB - 0.5
    fj = np.mod((ph + np.pi) / (2 * np.pi) * NB - 0.5, NB)
    i0 = np.clip(np.floor(fi).astype(int), 0, NB - 1); i1 = np.clip(i0 + 1, 0, NB - 1)
    j0 = np.floor(fj).astype(int) % NB; j1 = (j0 + 1) % NB
    a = fi - np.floor(fi); b = fj - np.floor(fj)

    def bil(A):
        return ((A[i0, j0] * (1 - a) + A[i1, j0] * a) * (1 - b)
                + (A[i0, j1] * (1 - a) + A[i1, j1] * a) * b)

    Hv = bil(Hs)
    tv = np.stack([bil(t) for t in tf])
    tv /= np.maximum(tv.sum(0, keepdims=True), 1e-9)
    return Vd, F, Hv, tv


def render_frame(Vd, F, Hv, tv, angle, size=440, alpha=0.28, ss=3):
    M = rmat_x(math.radians(-18)) @ rmat_z(angle) @ rmat_y(math.radians(24))
    R = 1 + alpha * (Hv - 0.5)
    P = Vd * R[:, None]
    Pr = P @ M.T
    Nr = Vd @ M.T
    f0, f1, f2 = F[:, 0], F[:, 1], F[:, 2]
    fn = np.cross(Pr[f1] - Pr[f0], Pr[f2] - Pr[f0])
    vn = np.zeros_like(Pr)
    np.add.at(vn, f0, fn); np.add.at(vn, f1, fn); np.add.at(vn, f2, fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
    flip = np.sum(vn * Nr, axis=1) < 0
    vn[flip] *= -1

    PIX = size * 0.47
    CX = CY = size / 2
    BIG = size * ss
    img = Image.new("RGB", (BIG, BIG), (5, 7, 13))
    msk = Image.new("L", (BIG, BIG), 0)
    drw, dmk = ImageDraw.Draw(img), ImageDraw.Draw(msk)
    sx = (CX + Pr[:, 0] * PIX) * ss
    sy = (CY - Pr[:, 1] * PIX) * ss
    sz = Pr[:, 2]

    keep = ((vn[f0, 2] + vn[f1, 2] + vn[f2, 2]) / 3) > 0.01
    Fv = F[keep]
    order = np.argsort((sz[Fv[:, 0]] + sz[Fv[:, 1]] + sz[Fv[:, 2]]) / 3)
    Fv = Fv[order]

    for tri in Fv:
        i, j, k = int(tri[0]), int(tri[1]), int(tri[2])
        n_ = vn[i] + vn[j] + vn[k]
        n_ /= max(np.linalg.norm(n_), 1e-12)
        diff = max(0.0, float(n_ @ LIGHT)); fill_ = max(0.0, float(n_ @ LIGHT2))
        spec = max(0.0, float(n_ @ HALF)) ** 34 * 0.16
        hf = (Hv[i] + Hv[j] + Hv[k]) / 3
        tvv = (tv[:, i] + tv[:, j] + tv[:, k]) / 3
        tint = (TINT * tvv[:, None]).sum(0)
        c = palette(np.array(hf)) * (0.55 + 0.45 * tint) * (0.40 + 0.70 * diff + 0.18 * fill_)
        rim = (1.0 - max(n_[2], 0.0)) ** 5 * 0.30
        c = np.clip(c + spec + rim * np.array([0.26, 0.46, 0.85]), 0, 1) * 255
        drw.polygon([(sx[i], sy[i]), (sx[j], sy[j]), (sx[k], sy[k])],
                    fill=(int(c[0]), int(c[1]), int(c[2])))
        dmk.polygon([(sx[i], sy[i]), (sx[j], sy[j]), (sx[k], sy[k])], fill=255)
    return img.filter(ImageFilter.GaussianBlur(ss * 0.5)).resize((size, size), Image.LANCZOS)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default=28, type=int)
    ap.add_argument("--size", default=440, type=int)
    ap.add_argument("--out", default="examples/rotating.gif", type=Path)
    a = ap.parse_args(argv)

    Vd, F, Hv, tv = build()
    imgs = []
    for i in range(a.frames):
        ang = 2 * math.pi * i / a.frames
        imgs.append(render_frame(Vd, F, Hv, tv, ang, size=a.size))
        print(f"  frame {i+1}/{a.frames}", end="\r")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    imgs[0].save(a.out, save_all=True, append_images=imgs[1:], duration=70, loop=0,
                 optimize=True, disposal=2)
    print(f"\nsaved {a.out}  {a.out.stat().st_size/1024:.0f} KB  ({a.frames} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())