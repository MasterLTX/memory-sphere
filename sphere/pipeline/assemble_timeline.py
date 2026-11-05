# -*- coding: utf-8 -*-
"""Assemble the single-file timeline page."""
import json
from pathlib import Path

import os
OUT = Path(os.environ.get("SPHERE_OUT", Path(__file__).resolve().parents[2] / "out"))
tpl = (OUT / "template_time.html").read_text(encoding="utf-8")
three = (OUT / "vendor" / "three.min.js").read_text(encoding="utf-8", errors="replace")
three = three.replace("</script", "<\\/script").replace("<!--", "<\\!--")
data = (OUT / "web_data.json").read_text(encoding="utf-8")
timef = (OUT / "time_frames.json").read_text(encoding="utf-8")

for ph in ("/*__THREE__*/", "/*__DATA__*/", "/*__TIME__*/"):
    assert ph in tpl, ph

out = (tpl.replace("/*__THREE__*/", three)
          .replace("/*__DATA__*/", data)
          .replace("/*__TIME__*/", timef))
dest = OUT / "sphere_timeline.html"
dest.write_text(out, encoding="utf-8")
print("sphere_timeline.html", dest.stat().st_size, "bytes")
meta = json.loads(timef)["meta"]
print("frames:", len(meta), meta[0]["date"], "->", meta[-1]["date"])