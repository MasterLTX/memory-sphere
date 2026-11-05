# -*- coding: utf-8 -*-
"""Render the bumpy sphere from height32.npy using an icosphere (no polar singularity).

Reads the height field produced by build_sphere.py, samples it at 10242 evenly
distributed icosphere vertices, displaces R, and paints with a painter's algorithm.
"""
import numpy as np, math, time, json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

import os
OUT = Path(os.environ.get("SPHERE_OUT", Path(__file__).resolve().parents[2] / "out"))
NB = 32
ALPHA = 0.28
R_BASE = 1.00
TYPE_MODE = "--type-color" in sys.argv
PURE = np.array([[0.82,0.64,0.33],[0.27,0.80,0.47],[1.00,0.33,0.26]])

t0 = time.time()
Hs = np.load(OUT / "height32.npy")
cnt = np.load(OUT / "count32.npy")
tf = np.load(OUT / "typefrac32.npy")     # (3,32,32)

# ---------------------------------------------------------------- icosphere
def icosphere(subdiv=5):
    t = (1 + math.sqrt(5)) / 2
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
         (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
         (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
         (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    V = [np.array(v, float) / np.linalg.norm(v) for v in V]
    for _ in range(subdiv):
        cache, newF = {}, []
        def mid(a, b):
            key = (a, b) if a < b else (b, a)
            if key in cache:
                return cache[key]
            m = V[a] + V[b]
            m /= np.linalg.norm(m)
            V.append(m)
            cache[key] = len(V) - 1
            return cache[key]
        for a, b, c in F:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            newF += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        F = newF
    return np.array(V), np.array(F, dtype=np.int64)

Vd, F = icosphere(5)
print(f"icosphere: {len(Vd)} verts, {len(F)} faces  ({time.time()-t0:.1f}s)")

# ---------------------------------------------------------------- sample the height field
x, y, z = Vd[:, 0], Vd[:, 1], Vd[:, 2]
th = np.arcsin(np.clip(z, -1, 1))
ph = np.arctan2(y, x)

fi = (th + np.pi / 2) / np.pi * NB - 0.5
fj = np.mod((ph + np.pi) / (2 * np.pi) * NB - 0.5, NB)
i0 = np.clip(np.floor(fi).astype(int), 0, NB - 1); i1 = np.clip(i0 + 1, 0, NB - 1)
j0 = np.floor(fj).astype(int) % NB; j1 = (j0 + 1) % NB
a = fi - np.floor(fi); b = fj - np.floor(fj)

def bil2(A):
    return ((A[i0, j0] * (1 - a) + A[i1, j0] * a) * (1 - b)
            + (A[i0, j1] * (1 - a) + A[i1, j1] * a) * b)

hv = bil2(Hs)
# one gentle 1-ring pass so displaced normals stay continuous (kills the facet sparkle)
for _ in range(1):
    acc = np.zeros(len(hv)); num = np.zeros(len(hv))
    for aa, bb in ((F[:, 0], F[:, 1]), (F[:, 0], F[:, 2]),
                   (F[:, 1], F[:, 0]), (F[:, 1], F[:, 2]),
                   (F[:, 2], F[:, 0]), (F[:, 2], F[:, 1])):
        np.add.at(acc, aa, hv[bb]); np.add.at(num, aa, 1.0)
    hv = 0.55 * hv + 0.45 * (acc / np.maximum(num, 1))
tv = np.stack([bil2(tf[k]) for k in range(3)])       # (3,V)
tv /= np.maximum(tv.sum(0, keepdims=True), 1e-9)

R = R_BASE + ALPHA * (hv - 0.5)
P = Vd * R[:, None]

# ---------------------------------------------------------------- camera
def rmat_z(ang):
    c, s = np.cos(ang), np.sin(ang); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
def rmat_y(ang):
    c, s = np.cos(ang), np.sin(ang); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
def rmat_x(ang):
    c, s = np.cos(ang), np.sin(ang); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])

M = rmat_x(np.deg2rad(-18)) @ rmat_z(np.deg2rad(-35)) @ rmat_y(np.deg2rad(24))
Pr = P @ M.T                     # rotated positions
Nr = Vd @ M.T                    # rotated unit directions

SCALE = 820
SS = 4
PIX = SCALE * 0.46
CX = CY = SCALE / 2
BIG = SCALE * SS

sx = (CX + Pr[:, 0] * PIX) * SS
sy = (CY - Pr[:, 1] * PIX) * SS
sz = Pr[:, 2]

# ---------------------------------------------------------------- palette
STOPS = np.array([
    [0.015, 0.030, 0.095],
    [0.030, 0.105, 0.270],
    [0.040, 0.230, 0.415],
    [0.060, 0.395, 0.435],
    [0.180, 0.560, 0.365],
    [0.510, 0.660, 0.290],
    [0.860, 0.715, 0.320],
    [1.000, 0.935, 0.770],
])
def palette(h):
    xq = np.clip(h, 0, 1) * (len(STOPS) - 1)
    i = np.clip(np.floor(xq).astype(int), 0, len(STOPS) - 2)
    f = (xq - i)[..., None]
    return STOPS[i] * (1 - f) + STOPS[i + 1] * f

TINT = np.array([[0.28, 0.52, 1.00], [0.34, 0.95, 0.58], [1.00, 0.40, 0.32]])
LIGHT = np.array([-0.40, 0.58, 0.71]); LIGHT /= np.linalg.norm(LIGHT)

# ---------------------------------------------------------------- sort + paint
f0, f1, f2 = F[:, 0], F[:, 1], F[:, 2]

# smooth vertex normals from the DISPLACED geometry, so hills actually catch light
fn = np.cross(Pr[f1] - Pr[f0], Pr[f2] - Pr[f0])
vn = np.zeros_like(Pr)
np.add.at(vn, f0, fn); np.add.at(vn, f1, fn); np.add.at(vn, f2, fn)
vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
# make sure they point outward
flip = np.sum(vn * Nr, axis=1) < 0
vn[flip] *= -1

nz_face = (vn[f0, 2] + vn[f1, 2] + vn[f2, 2]) / 3
front = nz_face > 0.01
Fv = F[front]
depth = (sz[Fv[:, 0]] + sz[Fv[:, 1]] + sz[Fv[:, 2]]) / 3
order = np.argsort(depth)
Fv = Fv[order]
print(f"front faces: {len(Fv)}  ({time.time()-t0:.1f}s)")

img = Image.new("RGB", (BIG, BIG), (0, 0, 0))
msk = Image.new("L", (BIG, BIG), 0)
drw, dmk = ImageDraw.Draw(img), ImageDraw.Draw(msk)

HALF = LIGHT + np.array([0.0, 0.0, 1.0]); HALF /= np.linalg.norm(HALF)
LIGHT2 = np.array([0.55, -0.62, 0.30]); LIGHT2 /= np.linalg.norm(LIGHT2)

for tri in Fv:
    i, j, k = int(tri[0]), int(tri[1]), int(tri[2])
    nrm = (vn[i] + vn[j] + vn[k])
    nrm /= max(np.linalg.norm(nrm), 1e-12)
    diff = max(0.0, float(nrm @ LIGHT))
    fill = max(0.0, float(nrm @ LIGHT2))
    spec = max(0.0, float(nrm @ HALF)) ** 34 * 0.16
    hface = (hv[i] + hv[j] + hv[k]) / 3
    tvec = (tv[:, i] + tv[:, j] + tv[:, k]) / 3
    rim = (1.0 - max(nrm[2], 0.0)) ** 5 * 0.30
    if TYPE_MODE:
        # height no longer drives hue: colour is the dominant memory type,
        # brightness still carries the relief so the terrain stays readable
        base = (PURE * tvec[:, None]).sum(0)
        c = base * (0.42 + 0.72 * hface) * (0.52 + 0.85 * diff + 0.20 * fill)
    else:
        tint = (TINT * tvec[:, None]).sum(0)
        base = palette(np.array(hface))
        c = base * (0.55 + 0.45 * tint) * (0.40 + 0.70 * diff + 0.18 * fill)
    c = c + spec + rim * np.array([0.26, 0.46, 0.85])
    c = np.clip(c, 0, 1) * 255
    # contour: darken triangles that straddle a height band edge
    band = np.floor(np.array([hv[i], hv[j], hv[k]]) * 8).astype(int)
    if band.min() != band.max():
        c = c * 0.84
    col = (int(c[0]), int(c[1]), int(c[2]))
    pts = [(sx[i], sy[i]), (sx[j], sy[j]), (sx[k], sy[k])]
    drw.polygon(pts, fill=col)
    dmk.polygon(pts, fill=255)

img = img.filter(ImageFilter.GaussianBlur(SS * 0.5)).resize((SCALE, SCALE), Image.LANCZOS)
msk = msk.filter(ImageFilter.GaussianBlur(SS * 0.5)).resize((SCALE, SCALE), Image.LANCZOS)
rgba = np.dstack([np.array(img), np.array(msk)])
name = "sphere_types_1024.png" if TYPE_MODE else "sphere_bumpy_1024.png"
Image.fromarray(rgba, "RGBA").save(OUT / name)
print(f"saved {name}  ({time.time()-t0:.1f}s)")

# stats for the write-up
flat = cnt.ravel()
print("bin stats: occupied=%d  max=%d  mean=%.1f  p90=%.0f  empty=%d"
      % ((flat > 0).sum(), flat.max(), flat.mean(), np.percentile(flat[flat > 0], 90), (flat == 0).sum()))