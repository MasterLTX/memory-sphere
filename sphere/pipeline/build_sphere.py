# -*- coding: utf-8 -*-
"""Build the 1024-anchor bumpy memory sphere from real Hindsight data.

pca50.npy -> PCA3 -> unit sphere -> 32x32 equal-area bins
-> per-bin aggregate (density, PageRank, entities, recency, type weight)
-> seam-aware spherical gaussian smoothing -> R = 1.05 + alpha*(h-0.5)
-> backface-culled painter's-algorithm sphere + unrolled 32x32 height map
"""
import numpy as np, json, time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

import os
OUT = Path(os.environ.get("SPHERE_OUT", Path(__file__).resolve().parents[2] / "out"))
import os
TMP = Path(os.environ.get("SPHERE_INPUT", Path(__file__).resolve().parents[2] / "data" / "input"))
NB = 32

t0 = time.time()

# ---------------------------------------------------------------- load
Y = np.load(OUT / "pca50.npy")
ids = np.load(OUT / "emb_ids.npy", allow_pickle=True)
types = np.load(OUT / "emb_types.npy", allow_pickle=True)
dates = np.load(OUT / "emb_dates.npy", allow_pickle=True)
N = len(ids)
idx_of = {u: k for k, u in enumerate(ids)}
print(f"N={N}  " + " ".join(f"{t}={int((types==t).sum())}" for t in sorted(set(types))))

Y3 = Y[:, :3].astype(np.float64)
Y3 -= Y3.mean(0)
P = Y3 / np.linalg.norm(Y3, axis=1, keepdims=True)

z = P[:, 2]
lam = np.arctan2(P[:, 1], P[:, 0])
bi = np.clip(((z + 1) / 2 * NB).astype(int), 0, NB - 1)
bj = np.clip(((lam + np.pi) / (2 * np.pi) * NB).astype(int), 0, NB - 1)
bin_id = bi * NB + bj
cnt = np.bincount(bin_id, minlength=NB * NB).astype(np.float64)

# ---------------------------------------------------------------- signals
src_l, dst_l, w_l = [], [], []
with open(TMP / "links.tsv", "r", encoding="utf-8") as f:
    for line in f:
        a = line.rstrip("\n").split("\t")
        if len(a) < 4:
            continue
        s = idx_of.get(a[0]); d = idx_of.get(a[1])
        if s is None or d is None:
            continue
        try:
            w = float(a[2])
        except ValueError:
            w = 1.0
        src_l.append(s); dst_l.append(d); w_l.append(w)
src = np.array(src_l, dtype=np.int64); dst = np.array(dst_l, dtype=np.int64)
wgt = np.array(w_l, dtype=np.float64)
print(f"links used: {len(src)}")

outdeg = np.bincount(src, weights=wgt, minlength=N)
pr = np.full(N, 1.0 / N)
for _ in range(60):
    contrib = pr[src] * wgt / np.maximum(outdeg[src], 1e-12)
    pr = (1 - 0.85) / N + 0.85 * np.bincount(dst, weights=contrib, minlength=N)
    pr /= pr.sum()
print(f"pagerank max={pr.max():.2e}  (uniform would be {1/N:.2e})")

ent = np.zeros(N)
with open(TMP / "ent_count.tsv", "r", encoding="utf-8") as f:
    for line in f:
        a = line.rstrip("\n").split("\t")
        if len(a) < 2:
            continue
        k = idx_of.get(a[0])
        if k is not None:
            try:
                ent[k] = float(a[1])
            except ValueError:
                pass

day = np.array([int(d[:4]) * 372 + int(d[5:7]) * 31 + int(d[8:10]) for d in dates], np.float64)
rec = np.exp(-(day.max() - day) / 45.0)

TW = {"observation": 1.0, "experience": 0.6, "world": 0.3}
tw = np.array([TW.get(t, 0.3) for t in types], np.float64)

def agg(v):
    return np.bincount(bin_id, weights=v, minlength=NB * NB) / np.maximum(cnt, 1)

pr_b, ent_b, rec_b, tw_b = agg(pr), agg(ent), agg(rec), agg(tw)

def rank01(v):
    return np.argsort(np.argsort(v)) / max(len(v) - 1, 1)

H = (0.30 * rank01(np.log1p(cnt)) + 0.25 * rank01(pr_b) + 0.15 * rank01(ent_b)
     + 0.10 * rank01(rec_b) + 0.20 * rank01(tw_b))
empty = cnt == 0

def fill_empty(A1, keep=0.88):
    """Empty anchors take the mean of their non-empty 3x3 neighbours (longitude
    wraps), scaled by `keep` so they still read as slightly low ground rather
    than fake hills. Replaces the old unconditional 0.35 dip."""
    A = A1.reshape(NB, NB).copy()
    em = empty.reshape(NB, NB)
    if not em.any() or em.all():
        return A.reshape(-1)
    acc = np.zeros_like(A); num = np.zeros_like(A)
    good = (~em).astype(np.float64)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            if di == 0 and dj == 0:
                continue
            acc += np.roll(np.roll(np.where(em, 0.0, A), di, 0), dj, 1)
            num += np.roll(np.roll(good, di, 0), dj, 1)
    fallback = A[~em].mean() if (~em).any() else 0.0
    filled = np.where(num > 0, acc / np.maximum(num, 1e-9), fallback)
    A[em] = filled[em] * keep
    return A.reshape(-1)
H[empty] = 0.0

tmap = {t: k for k, t in enumerate(["world", "experience", "observation"])}
tcode = np.array([tmap.get(t, 0) for t in types])
type_frac = np.zeros((3, NB * NB))
for k in range(3):
    m = tcode == k
    type_frac[k] = np.bincount(bin_id[m], minlength=NB * NB)
type_frac /= np.maximum(type_frac.sum(0, keepdims=True), 1)

# mental models -> peaks
mm_pos = []
try:
    comp = np.load(OUT / "pca_components.npy")
    raw, names = [], []
    with open(TMP / "models.tsv", "r", encoding="utf-8") as f:
        for line in f:
            a = line.rstrip("\n").split("\t")
            if len(a) < 2:
                continue
            names.append(a[0])
            raw.append(np.fromstring(a[1][1:-1], dtype=np.float32, sep=","))
    M = np.vstack(raw)
    M3 = (M @ comp)[:, :3].astype(np.float64)
    M3 -= M3.mean(0)
    Mn = M3 / np.maximum(np.linalg.norm(M3, axis=1, keepdims=True), 1e-9)
    mm_pos = Mn
    mz = Mn[:, 2]; ml = np.arctan2(Mn[:, 1], Mn[:, 0])
    mi = np.clip(((mz + 1) / 2 * NB).astype(int), 0, NB - 1)
    mj = np.clip(((ml + np.pi) / (2 * np.pi) * NB).astype(int), 0, NB - 1)
    H = H + np.bincount(mi * NB + mj, minlength=NB * NB) * 0.05
    print(f"mental_models: {len(names)}")
except Exception as e:
    print("mental_models skipped:", e)

H = (H - H.min()) / max(H.max() - H.min(), 1e-9)
H = fill_empty(H)

def gkern(sigma, rad=3):
    x = np.arange(-rad, rad + 1)
    k = np.exp(-x ** 2 / (2 * sigma ** 2)); return k / k.sum()

def smooth(A, sigma=1.2):
    k = gkern(sigma); rad = len(k) // 2
    # longitude: circular
    out = np.zeros_like(A)
    for t, wt in zip(range(-rad, rad + 1), k):
        out += wt * np.roll(A, t, axis=1)
    A = out
    # latitude: edge-padded
    n = A.shape[0]
    Pd = np.pad(A, ((rad, rad), (0, 0)), mode="edge")
    out = np.zeros_like(A)
    for t, wt in zip(range(-rad, rad + 1), k):
        out += wt * Pd[rad + t: rad + t + n, :]
    return out

Hr = H.reshape(NB, NB)
base = smooth(Hr, 0.9)                       # continental scale
fine = smooth(Hr, 0.6) - smooth(Hr, 2.2)     # band-pass: the small hills
fr = fine.max() - fine.min()
fine = (fine - fine.min()) / fr - 0.5 if fr > 1e-9 else np.zeros_like(fine)
Hs = base + 0.34 * fine
hmin, hmax = Hs.min(), Hs.max()
Hs = (Hs - hmin) / max(hmax - hmin, 1e-9)
hfig = Hs.ravel()
def mk_layer(v):
    A = fill_empty((v - v.min()) / max(v.max() - v.min(), 1e-9)).reshape(NB, NB)
    baseL = smooth(A, 0.9)
    fineL = smooth(A, 0.6) - smooth(A, 2.2)
    fr2 = fineL.max() - fineL.min()
    fineL = (fineL - fineL.min()) / fr2 - 0.5 if fr2 > 1e-9 else np.zeros_like(fineL)
    o = baseL + 0.34 * fineL
    return (o - o.min()) / max(o.max() - o.min(), 1e-9)

for k, v in {"density": np.log1p(cnt), "pagerank": pr_b, "entities": ent_b,
             "recency": rec_b, "typew": tw_b}.items():
    np.save(OUT / ("layer_%s.npy" % k), mk_layer(v))

np.save(OUT / "height32.npy", Hs)
np.save(OUT / "count32.npy", cnt.reshape(NB, NB))
np.save(OUT / "typefrac32.npy", type_frac.reshape(3, NB, NB))
np.save(OUT / "bin_id.npy", bin_id)
print(f"height field: min={hfig.min():.3f} max={hfig.max():.3f} mean={hfig.mean():.3f}")

STOPS = np.array([
    [0.015, 0.030, 0.095], [0.030, 0.105, 0.270], [0.040, 0.230, 0.415],
    [0.060, 0.395, 0.435], [0.180, 0.560, 0.365], [0.510, 0.660, 0.290],
    [0.860, 0.715, 0.320], [1.000, 0.935, 0.770],
])
def palette(h):
    xq = np.clip(h, 0, 1) * (len(STOPS) - 1)
    i = np.clip(np.floor(xq).astype(int), 0, len(STOPS) - 2)
    f = (xq - i)[..., None]
    return STOPS[i] * (1 - f) + STOPS[i + 1] * f

# ---------------------------------------------------------------- unrolled
side = 1024
himg = Image.fromarray((Hs.T[::-1] * 255).astype(np.uint8), "L").resize((side, side), Image.BICUBIC)
hup = np.array(himg, np.float64) / 255.0
rgb2 = (np.clip(palette(hup), 0, 1) * 255).astype(np.uint8)
band = np.floor(hup * 8)
e0 = band != np.vstack([band[:1], band[:-1]])
e1 = band != np.hstack([band[:, :1], band[:, :-1]])
edge = e0 | e1
rgb2[edge] = (rgb2[edge] * 0.78).astype(np.uint8)
step = side // NB
for g in range(0, side, step * 4):
    rgb2[g:g + 1, :, :] = (rgb2[g:g + 1, :, :] * 0.74).astype(np.uint8)
    rgb2[:, g:g + 1, :] = (rgb2[:, g:g + 1, :] * 0.74).astype(np.uint8)
Image.fromarray(rgb2, "RGB").save(OUT / "sphere_unrolled_32x32.png")
print("saved sphere_unrolled_32x32.png")

json.dump({
    "units": int(N),
    "bins_occupied": int((cnt > 0).sum()),
    "bin_count_max": int(cnt.max()),
    "bin_count_mean": float(cnt.mean()),
    "height_min": float(hfig.min()), "height_max": float(hfig.max()),
    "alpha": 0.28, "r_base": 1.00,   # displacement used by render_sphere.py
    "type_counts": {str(t): int((types == t).sum()) for t in set(types)},
    "links_used": int(len(src)),
    "pagerank_max": float(pr.max()),
}, open(OUT / "stats.json", "w"), indent=2)
print("done", round(time.time() - t0, 1), "s")