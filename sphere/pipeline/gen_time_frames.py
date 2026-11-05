# -*- coding: utf-8 -*-
"""Time-sliced cumulative height field: 25 frames, one per day that has memories.

Sphere positions are FIXED (global PCA3 binning) - only the height field evolves,
so the animation shows the same territory rising and sinking, not points jumping.

All frames share ONE global normalisation scale, so early frames really are
darker/flatter instead of being rescaled to look as mature as the last frame.
"""
import numpy as np, base64, json, time
from pathlib import Path

import os
OUT = Path(os.environ.get("SPHERE_OUT", Path(__file__).resolve().parents[2] / "out"))
import os
TMP = Path(os.environ.get("SPHERE_INPUT", Path(__file__).resolve().parents[2] / "data" / "input"))
NB = 32
t0 = time.time()

Y = np.load(OUT / "pca50.npy")
ids = np.load(OUT / "emb_ids.npy", allow_pickle=True)
types = np.load(OUT / "emb_types.npy", allow_pickle=True)
dates = list(np.load(OUT / "emb_dates.npy", allow_pickle=True))
N = len(ids)
idx_of = {u: k for k, u in enumerate(ids)}

# ---- fixed sphere positions (same maths as build_sphere.py) ----
Y3 = Y[:, :3].astype(np.float64); Y3 -= Y3.mean(0)
P = Y3 / np.linalg.norm(Y3, axis=1, keepdims=True)
zz = P[:, 2]; lam = np.arctan2(P[:, 1], P[:, 0])
bi = np.clip(((zz + 1) / 2 * NB).astype(int), 0, NB - 1)
bj = np.clip(((lam + np.pi) / (2 * np.pi) * NB).astype(int), 0, NB - 1)
bin_id = bi * NB + bj

# ---- graph ----
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
src = np.array(src_l, np.int64); dst = np.array(dst_l, np.int64); wgt = np.array(w_l, np.float64)
print(f"links: {len(src)}")

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
TW = {"observation": 1.0, "experience": 0.6, "world": 0.3}
tw = np.array([TW.get(t, 0.3) for t in types], np.float64)

frames_day = sorted(set(dates))
print(f"frames: {len(frames_day)}  {frames_day[0]} -> {frames_day[-1]}")

def pagerank(mask):
    keep = mask[src] & mask[dst]
    s, d2, w = src[keep], dst[keep], wgt[keep]
    m = mask.astype(np.float64)
    if len(s) == 0:
        return m / max(m.sum(), 1)
    od = np.bincount(s, weights=w, minlength=N)
    pr = m / max(m.sum(), 1)
    for _ in range(30):
        contrib = pr[s] * w / np.maximum(od[s], 1e-12)
        pr = 0.15 / N + 0.85 * np.bincount(d2, weights=contrib, minlength=N)
        pr *= m
        tot = pr.sum()
        if tot > 0:
            pr /= tot
    return pr

def agg(vals, mask, denom):
    s = np.bincount(bin_id[mask], weights=vals[mask], minlength=NB * NB)
    return s / np.maximum(denom, 1)

def gkern(sigma, rad=3):
    x = np.arange(-rad, rad + 1); k = np.exp(-x ** 2 / (2 * sigma ** 2)); return k / k.sum()

def smooth(A, sigma=0.9):
    k = gkern(sigma); rad = len(k) // 2
    out = np.zeros_like(A)
    for t, wt_ in zip(range(-rad, rad + 1), k):
        out += wt_ * np.roll(A, t, axis=1)
    A = out
    n = A.shape[0]
    Pd = np.pad(A, ((rad, rad), (0, 0)), mode="edge")
    out = np.zeros_like(A)
    for t, wt_ in zip(range(-rad, rad + 1), k):
        out += wt_ * Pd[rad + t: rad + t + n, :]
    return out

# ---- global scale, taken from the FULL data ----
full = np.ones(N, bool)
cnt_full = np.bincount(bin_id, minlength=NB * NB).astype(np.float64)
pr_full = agg(pagerank(full), full, np.maximum(cnt_full, 1))
ent_full = agg(ent, full, np.maximum(cnt_full, 1))
tw_full = agg(tw, full, np.maximum(cnt_full, 1))
rec_full = np.ones(NB * NB)

def q(v, p):
    return float(np.percentile(v, p))
recv_full = np.exp(-(day.max() - day) / 45.0)
recb_full = agg(recv_full, full, np.maximum(cnt_full, 1))
SCALE = {
    "cnt": (np.log1p(cnt_full), q(np.log1p(cnt_full), 3), q(np.log1p(cnt_full), 97)),
    "pr":  (pr_full, q(pr_full, 3), q(pr_full, 97)),
    "ent": (ent_full, q(ent_full, 3), q(ent_full, 97)),
    "tw":  (tw_full, q(tw_full, 3), q(tw_full, 97)),
    "rec": (recb_full, q(recb_full, 3), q(recb_full, 97)),
}
def nrm(key, v):
    _, lo, hi = SCALE[key]
    return np.clip((v - lo) / max(hi - lo, 1e-9), 0, 1)

W = {"cnt": 0.30, "pr": 0.25, "ent": 0.15, "rec": 0.10, "tw": 0.20}

def frame_H(mask, dnow):
    c = np.bincount(bin_id[mask], minlength=NB * NB).astype(np.float64)
    den = np.maximum(c, 1)
    prb = agg(pagerank(mask), mask, den)
    entb = agg(ent, mask, den)
    twb = agg(tw, mask, den)
    recv = np.exp(-(dnow - day) / 45.0)
    recb = agg(recv, mask, den)
    Hc = (W["cnt"] * nrm("cnt", np.log1p(c)) + W["pr"] * nrm("pr", prb)
          + W["ent"] * nrm("ent", entb) + W["rec"] * nrm("rec", recb)
          + W["tw"] * nrm("tw", twb))
    Hc = np.where(c > 0, Hc, 0.0)
    em = (c == 0)
    A = Hc.reshape(NB, NB)
    if em.any() and (~em).any():
        em2 = em.reshape(NB, NB)
        acc = np.zeros_like(A); num = np.zeros_like(A); good = (~em2).astype(float)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                acc += np.roll(np.roll(np.where(em2, 0.0, A), di, 0), dj, 1)
                num += np.roll(np.roll(good, di, 0), dj, 1)
        fb = A[~em2].mean()
        A = np.where(em2, np.where(num > 0, acc / np.maximum(num, 1e-9), fb) * 0.88, A)
        Hc = A.reshape(-1)
    base = smooth(A, 0.9)
    fine = smooth(A, 0.6) - smooth(A, 2.2)
    return base.reshape(-1), fine.reshape(-1), c

# full-data reference for the band-pass amplitude
_, fine_full, _ = frame_H(full, day.max())
FSCALE = np.percentile(np.abs(fine_full), 99) or 1.0

frames, meta = [], []
for dstr in frames_day:
    dnow = int(dstr[:4]) * 372 + int(dstr[5:7]) * 31 + int(dstr[8:10])
    mask = day <= dnow
    base, fine, c = frame_H(mask, dnow)
    H = base + 0.34 * (fine / FSCALE) * 0.5
    H = np.clip(H, 0, 1)
    frames.append(H)
    meta.append({"date": dstr, "cum": int(mask.sum()),
                 "bins": int((c > 0).sum()), "peak": float(H.max())})
    print(f"  {dstr}  cum={int(mask.sum()):5d}  bins={int((c>0).sum()):4d}  Hmax={H.max():.3f}  "
          f"({time.time()-t0:.1f}s)")

# pack: 25 x 1024 uint8 -> base64 per frame
packed = [base64.b64encode((H * 255).round().astype(np.uint8).tobytes()).decode() for H in frames]
out = {"frames": packed, "meta": meta}
p = OUT / "time_frames.json"
p.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
print("time_frames.json", p.stat().st_size, "bytes;", len(frames), "frames")