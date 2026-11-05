# -*- coding: utf-8 -*-
"""Export the sphere's 1024 bins as packed base64 for the interactive page."""
import numpy as np, base64, json
from pathlib import Path

import os
OUT = Path(os.environ.get("SPHERE_OUT", Path(__file__).resolve().parents[2] / "out"))

def enc(a):
    a = np.clip(np.asarray(a, dtype=np.float64), 0.0, 1.0)
    return base64.b64encode((a * 255).round().astype(np.uint8).tobytes()).decode()

h = np.load(OUT / "height32.npy").ravel()
cnt = np.load(OUT / "count32.npy").ravel()
tf = np.load(OUT / "typefrac32.npy").reshape(3, -1)
nmax = float(cnt.max()) or 1.0

layers = {}
for k in ["density", "pagerank", "entities", "recency", "typew"]:
    layers[k] = enc(np.load(OUT / f"layer_{k}.npy").ravel())

data = {
    "h": enc(h),
    "count": enc(cnt / nmax),
    "nmax": int(cnt.max()),
    "types": [enc(tf[0]), enc(tf[1]), enc(tf[2])],
    "layers": layers,
}
p = OUT / "web_data.json"
p.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
print("web_data.json", p.stat().st_size, "bytes")

# ---- assemble the single-file page ----
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
tpl = (HERE / "template.html").read_text(encoding="utf-8")
three = (ROOT / "vendor" / "three.min.js").read_text(encoding="utf-8", errors="replace")
three = three.replace("</script", "<\\/script").replace("<!--", "<\\!--")
assert "/*__THREE__*/" in tpl and "/*__DATA__*/" in tpl
out = tpl.replace("/*__THREE__*/", three).replace("/*__DATA__*/", p.read_text(encoding="utf-8"))
dest = OUT / "sphere_interactive.html"
dest.write_text(out, encoding="utf-8")
print("sphere_interactive.html", dest.stat().st_size, "bytes")