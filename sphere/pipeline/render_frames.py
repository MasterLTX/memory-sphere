# -*- coding: utf-8 -*-
"""Render N time frames from time_frames.json into one comparison sheet."""
import numpy as np, json, base64, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

import os
OUT = Path(os.environ.get("SPHERE_OUT", Path(__file__).resolve().parents[2] / "out"))
NB = 32
ALPHA, R_BASE = 0.28, 1.00
PICK = [0, 6, 12, 17, 20, 24]          # 6 moments spanning the 25 frames

frames_raw = json.loads((OUT / "time_frames.json").read_text(encoding="utf-8"))
def dec(b64):
    a = np.frombuffer(base64.b64decode(b64), dtype=np.uint8)
    return (a / 255.0).reshape(NB, NB)
FR = [dec(f) for f in frames_raw["frames"]]
META = frames_raw["meta"]

# ---- icosphere ----
def icosphere(subdiv=5):
    t = (1 + math.sqrt(5)) / 2
    V = [(-1,t,0),(1,t,0),(-1,-t,0),(1,-t,0),(0,-1,t),(0,1,t),(0,-1,-t),(0,1,-t),(t,0,-1),(t,0,1),(-t,0,-1),(-t,0,1)]
    F = [(0,11,5),(0,5,1),(0,1,7),(0,7,10),(0,10,11),(1,5,9),(5,11,4),(11,10,2),(10,7,6),(7,1,8),
         (3,9,4),(3,4,2),(3,2,6),(3,6,8),(3,8,9),(4,9,5),(2,4,11),(6,2,10),(8,6,7),(9,8,1)]
    V = [np.array(v, float)/np.linalg.norm(v) for v in V]
    for _ in range(subdiv):
        cache, newF = {}, []
        def mid(a,b):
            k=(a,b) if a<b else (b,a)
            if k in cache: return cache[k]
            m=V[a]+V[b]; m/=np.linalg.norm(m); V.append(m); cache[k]=len(V)-1; return cache[k]
        for a,b,c in F:
            ab,bc,ca=mid(a,b),mid(b,c),mid(c,a)
            newF += [(a,ab,ca),(b,bc,ab),(c,ca,bc),(ab,bc,ca)]
        F=newF
    return np.array(V), np.array(F, np.int64)

Vd, F = icosphere(5)          # 20480 faces: smooth enough at 420px

STOPS = np.array([[0.015,0.030,0.095],[0.030,0.105,0.270],[0.040,0.230,0.415],[0.060,0.395,0.435],
                  [0.180,0.560,0.365],[0.510,0.660,0.290],[0.860,0.715,0.320],[1.000,0.935,0.770]])
def palette(h):
    x = np.clip(h,0,1)*(len(STOPS)-1)
    i = np.clip(np.floor(x).astype(int),0,len(STOPS)-2)
    f = (x-i)[...,None]
    return STOPS[i]*(1-f)+STOPS[i+1]*f
TINT = np.array([[0.28,0.52,1.00],[0.34,0.95,0.58],[1.00,0.40,0.32]])
LIGHT = np.array([-0.40,0.58,0.71]); LIGHT/=np.linalg.norm(LIGHT)
HALF = LIGHT+np.array([0,0,1.0]); HALF/=np.linalg.norm(HALF)
LIGHT2 = np.array([0.55,-0.62,0.30]); LIGHT2/=np.linalg.norm(LIGHT2)

def rmat(v):
    c,s = np.cos(v), np.sin(v)
    if v[0]: return np.array([[1,0,0],[0,c,-s],[0,s,c]])
def rmat_x(a):
    c,s=np.cos(a),np.sin(a); return np.array([[1,0,0],[0,c,-s],[0,s,c]])
def rmat_y(a):
    c,s=np.cos(a),np.sin(a); return np.array([[c,0,s],[0,1,0],[-s,0,c]])
def rmat_z(a):
    c,s=np.cos(a),np.sin(a); return np.array([[c,-s,0],[s,c,0],[0,0,1]])
M = rmat_x(math.radians(-18)) @ rmat_z(math.radians(-35)) @ rmat_y(math.radians(24))

x,y,z = Vd[:,0],Vd[:,1],Vd[:,2]
th = np.arcsin(np.clip(z,-1,1)); ph = np.arctan2(y,x)
fi = (th+np.pi/2)/np.pi*NB-0.5
fj = np.mod((ph+np.pi)/(2*np.pi)*NB-0.5, NB)
i0 = np.clip(np.floor(fi).astype(int),0,NB-1); i1 = np.clip(i0+1,0,NB-1)
j0 = np.floor(fj).astype(int)%NB; j1=(j0+1)%NB
a = fi-np.floor(fi); b = fj-np.floor(fj)

tf = np.load(OUT/"typefrac32.npy").reshape(3,NB,NB)
tv = np.stack([((A[i0,j0]*(1-a)+A[i1,j0]*a)*(1-b)+(A[i0,j1]*(1-a)+A[i1,j1]*a)*b) for A in tf])
tv /= np.maximum(tv.sum(0,keepdims=True),1e-9)

Nr = Vd @ M.T
SZ = (Vd*1.0) @ M.T
f0,f1,f2 = F[:,0],F[:,1],F[:,2]

def render(Hs, size=420, ss=3):
    Hv = ((Hs[i0,j0]*(1-a)+Hs[i1,j0]*a)*(1-b)+(Hs[i0,j1]*(1-a)+Hs[i1,j1]*a)*b)
    # light 1-ring smoothing
    for _ in range(1):
        acc=np.zeros(len(Hv)); num=np.zeros(len(Hv))
        for aa,bb in ((f0,f1),(f0,f2),(f1,f0),(f1,f2),(f2,f0),(f2,f1)):
            np.add.at(acc,aa,Hv[bb]); np.add.at(num,aa,1.0)
        Hv = 0.55*Hv+0.45*(acc/np.maximum(num,1))
    Rr = R_BASE + ALPHA*(Hv-0.5)
    P = Vd*Rr[:,None]
    Pr = P @ M.T
    nrm_f = np.cross(Pr[f1]-Pr[f0], Pr[f2]-Pr[f0])
    vn = np.zeros_like(Pr)
    np.add.at(vn,f0,nrm_f); np.add.at(vn,f1,nrm_f); np.add.at(vn,f2,nrm_f)
    vn /= np.maximum(np.linalg.norm(vn,axis=1,keepdims=True),1e-12)
    flip = np.sum(vn*Nr,axis=1)<0; vn[flip]*=-1

    PIX = size*0.47; CX=CY=size/2; BIG=size*ss
    img = Image.new("RGB",(BIG,BIG),(5,7,13)); msk = Image.new("L",(BIG,BIG),0)
    drw, dmk = ImageDraw.Draw(img), ImageDraw.Draw(msk)
    sx = (CX+Pr[:,0]*PIX)*ss; sy=(CY-Pr[:,1]*PIX)*ss; sz=Pr[:,2]

    nzf = (vn[f0,2]+vn[f1,2]+vn[f2,2])/3
    keep = nzf>0.01
    Fv = F[keep]
    order = np.argsort((sz[Fv[:,0]]+sz[Fv[:,1]]+sz[Fv[:,2]])/3)
    Fv = Fv[order]
    for tri in Fv:
        i,j,k = int(tri[0]),int(tri[1]),int(tri[2])
        n_ = vn[i]+vn[j]+vn[k]; n_/=max(np.linalg.norm(n_),1e-12)
        diff=max(0.0,float(n_@LIGHT)); fill_=max(0.0,float(n_@LIGHT2))
        spec=max(0.0,float(n_@HALF))**34*0.16
        hf=(Hv[i]+Hv[j]+Hv[k])/3
        tvv=(tv[:,i]+tv[:,j]+tv[:,k])/3
        tint=(TINT*tvv[:,None]).sum(0)
        c = palette(np.array(hf))*(0.55+0.45*tint)*(0.40+0.70*diff+0.18*fill_)
        rim=(1.0-max(n_[2],0.0))**5*0.30
        c = c+spec+rim*np.array([0.26,0.46,0.85])
        c = np.clip(c,0,1)*255
        col=(int(c[0]),int(c[1]),int(c[2]))
        pts=[(sx[i],sy[i]),(sx[j],sy[j]),(sx[k],sy[k])]
        drw.polygon(pts,fill=col); dmk.polygon(pts,fill=255)
    img = img.filter(ImageFilter.GaussianBlur(ss*0.5)).resize((size,size),Image.LANCZOS)
    msk = msk.filter(ImageFilter.GaussianBlur(ss*0.5)).resize((size,size),Image.LANCZOS)
    return Image.fromarray(np.dstack([np.array(img),np.array(msk)]),"RGBA")

# ---- sheet ----
CELL, PAD, TOP = 420, 26, 64
COLS, ROWS = 3, 2
W = PAD + COLS*(CELL+PAD)
H = TOP + ROWS*(CELL+52)
sheet = Image.new("RGB",(W,H),(5,7,13))
dr = ImageDraw.Draw(sheet)
dr.text((PAD, 22), "MEMORY SPHERE  ·  cumulative height field  ·  25 daily frames, 6 shown",
        fill=(150,180,215))
try:
    from PIL import ImageFont
    font_big = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 17)
    font_sm  = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 13)
except Exception:
    font_big = font_sm = None

for n, idx in enumerate(PICK):
    r, c = divmod(n, COLS)
    x0 = PAD + c*(CELL+PAD); y0 = TOP + r*(CELL+52)
    im = render(FR[idx], CELL)
    sheet.paste(im, (x0, y0), im)
    m = META[idx]
    dr.text((x0+2, y0+CELL+8), m["date"], fill=(205,225,245), font=font_big)
    dr.text((x0+2, y0+CELL+30), f'{m["cum"]:,} memories · {m["bins"]}/1024 anchors · peak {m["peak"]:.2f}',
            fill=(110,135,165), font=font_sm)

out = OUT / "sphere_timeline_sheet.png"
sheet.save(out)
print("saved", out.name, sheet.size)