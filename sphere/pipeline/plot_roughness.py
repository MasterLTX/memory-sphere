# -*- coding: utf-8 -*-
"""Terrain roughness over time: is the sphere really getting smoother?"""
import numpy as np, json, base64
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

import os
OUT = Path(os.environ.get("SPHERE_OUT", Path(__file__).resolve().parents[2] / "out"))
NB = 32
d = json.loads((OUT / "time_frames.json").read_text(encoding="utf-8"))
def dec(b): return (np.frombuffer(base64.b64decode(b), np.uint8) / 255.0).reshape(NB, NB)

rows = []
for fr, m in zip(d["frames"], d["meta"]):
    H = dec(fr)
    lap = 4*H - (np.roll(H, 1, 0) + np.roll(H, -1, 0) + np.roll(H, 1, 1) + np.roll(H, -1, 1))
    rows.append({"date": m["date"], "cum": m["cum"], "bins": m["bins"],
                 "rough": float(np.sqrt((lap**2).mean())), "std": float(H.std())})

W, H_ = 1180, 560
PADL, PADR, PADT, PADB = 86, 40, 74, 78
img = Image.new("RGB", (W, H_), (6, 9, 16))
dr = ImageDraw.Draw(img)
try:
    f_big = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 21)
    f_md = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 14)
    f_sm = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 12)
    f_cn = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)
except Exception:
    f_big = f_md = f_sm = f_cn = None

rough = np.array([r["rough"] for r in rows])
cm = np.array([r["cum"] for r in rows])
n = len(rows)
x0, x1 = PADL, W - PADR
y0, y1 = PADT, H_ - PADB
rmax = rough.max() * 1.16
def X(i): return x0 + (x1 - x0) * i / (n - 1)
def Y(v): return y1 - (y1 - y0) * v / rmax

# grid
for g in range(5):
    v = rmax * g / 4
    yy = Y(v)
    dr.line([(x0, yy), (x1, yy)], fill=(20, 27, 40))
    dr.text((x0 - 12, yy - 7), f"{v:.3f}", fill=(86, 102, 124), font=f_sm, anchor="ra")

# roughness area + line
pts = [(X(i), Y(rough[i])) for i in range(n)]
dr.polygon(pts + [(X(n-1), y1), (X(0), y1)], fill=(22, 40, 66))
dr.line(pts, fill=(96, 176, 255), width=2, joint="curve")
for i, (px, py) in enumerate(pts):
    r = 3.4 if i not in (7, n-1) else 4.6
    dr.ellipse([px-r, py-r, px+r, py+r], fill=(150, 210, 255))

# cumulative memory on the same axis (scaled, dashed feel via dots)
cmax = cm.max()
for i in range(n):
    yy = y1 - (y1 - y0) * (cm[i] / cmax) * 0.92
    dr.ellipse([X(i)-1.6, yy-1.6, X(i)+1.6, yy+1.6], fill=(70, 110, 96))

# peak marker
pk = int(np.argmax(rough))
dr.line([(X(pk), Y(rough[pk])), (X(pk), y1)], fill=(120, 90, 60), width=1)
dr.text((X(pk)+8, Y(rough[pk])-24), f"roughness peaks {rough[pk]:.3f} @ {rows[pk]['date']}",
        fill=(226, 178, 120), font=f_sm)

# annotations
dr.text((X(0), Y(rough[0])-26), f"{rough[0]:.3f}", fill=(150, 210, 255), font=f_sm)
dr.text((X(n-1)-10, Y(rough[-1])-26), f"{rough[-1]:.3f}", fill=(150, 210, 255), font=f_sm, anchor="ra")
dr.text((PADL, 24), "TERRAIN ROUGHNESS  vs  CUMULATIVE MEMORIES", fill=(168, 196, 226), font=f_big)
dr.text((PADL, 50), "roughness = RMS(Laplacian h) over the 32x32 field   ·   dots = cumulative memory count",
        fill=(96, 116, 140), font=f_sm)

# x labels
for i in (0, 6, 12, 18, n-1):
    dr.text((X(i), y1 + 12), rows[i]["date"][5:], fill=(96, 116, 140), font=f_sm, anchor="mt")
dr.text((PADL, y1 + 40), "first 3 weeks: filling empty bins makes the surface ROUGHER", fill=(150, 170, 196), font=f_sm)
dr.text((PADL, y1 + 58), "after 10-12: every bin holds ~10 memories, averages converge, surface FLATTENS",
        fill=(150, 170, 196), font=f_sm)

out = OUT / "roughness_curve.png"
img.save(out)
print("saved", out.name, img.size)
print("peak:", rows[pk]["date"], round(rough[pk], 4), "| first:", round(rough[0],4),
      "| last:", round(rough[-1],4),
      "| drop from peak: %.1f%%" % ((rough[pk]-rough[-1])/rough[pk]*100),
      "| rise from start: +%.1f%%" % ((rough[pk]-rough[0])/rough[0]*100))
json.dump(rows, open(OUT / "roughness.json", "w"), indent=1)