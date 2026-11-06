# -*- coding: utf-8 -*-
"""Gate for the built deck: do the four render additions actually exist in
`out/sphere_timeline.html`, and did the build consume its placeholders?

This is a build gate, not a look-at-it gate. It parses the single-file deck as
text and checks the things a missing `assemble_timeline.py` substitution or a
leftover stub would break, none of which need a browser:

  starfield   `const STARS = (function(` and the tier table that sizes it
  ocean       a `THREE.ShaderMaterial` bound to `waterMesh`-style water geometry,
              added to the scene
  glow        the crest glow shell mesh, added to the scene
  snow line   `SNOW_TOP` and `snowLineOf`, the palette band above the snow line
  displace    the height formula `1 + alpha*(h-0.5)` still present in its
              original spelling, and EVERY `alpha*(h - X)` site in the file
              still uses X = 0.5 -- a rewritten constant is a silent change of
              the terrain, and it would make the README's arithmetic wrong
  build       `/*__THREE__*/`, `/*__DATA__*/`, `/*__TIME__*/` all consumed --
              a placeholder that survives means the page ships with no data
  size        under 1.2 MB (1,258,291 bytes), so the single-file deck stays
              loadable as one request

Identifiers are matched loosely (name + a few characters of structure, not whole
lines) so a comment or a reformat does not fail the gate, while a renamed or
deleted feature does.

Usage
    python scripts/check_render.py [--deck out/sphere_timeline.html] [--max-bytes N]

Exit code 0 = every addition present and the deck within budget, 1 = something
is missing or over budget, 2 = the deck file does not exist.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAX = int(1.2 * 1024 * 1024)   # 1,258,291 bytes

# (group, label, pattern, how many times it must match)
REQUIRED = [
    ("starfield", "STARS tier block", r"const\s+STARS\s*=\s*\(function", 1),
    ("starfield", "star tier table", r"const\s+tiers\s*=\s*\[", 1),
    ("ocean", "water ShaderMaterial",
     r"const\s+waterMat\s*=\s*new\s+THREE\.ShaderMaterial\s*\(", 1),
    ("ocean", "water added to scene", r"scene\.add\(\s*water\s*\)", 1),
    ("glow", "glow shell mesh", r"const\s+glowMesh\s*=\s*new\s+THREE\.Mesh", 1),
    ("glow", "glow ShaderMaterial",
     r"const\s+glowMat\s*=\s*new\s+THREE\.ShaderMaterial\s*\(", 1),
    ("glow", "glow added to scene", r"scene\.add\(\s*glowMesh\s*\)", 1),
    ("snow", "snow-line constant", r"const\s+SNOW_TOP\s*=", 1),
    ("snow", "snow-line function", r"function\s+snowLineOf\s*\(", 1),
    ("displace", "height formula verbatim",
     r"1 \+ alpha\*\(h-0\.5\)", 1),
    # --- cloud shell (v1.2) -------------------------------------------------------
    # These target the two failures that DO NOT throw. A fragment shader that fails to
    # compile draws nothing and logs to console.error, which this deck never reads; a
    # second geometry handed the terrain's index ATTRIBUTE fights it for one VAO
    # binding and rasterises with the wrong vertices. Both look exactly like "the cloud
    # is not there", and both cost an afternoon to find without an assertion.
    ("cloud", "cloud ShaderMaterial",
     r"cloudMat\s*=\s*new\s+THREE\.ShaderMaterial\s*\(", 1),
    ("cloud", "cloud field textures wired", r"uBig:\s*\{", 1),
    ("cloud", "cloud small-scale texture wired", r"uSmall:\s*\{", 1),
    ("cloud", "cloud shell added to scene", r"scene\.add\(\s*cloudPts\s*\)", 1),
    # the shell must reuse the terrain topology by ARRAY, never the index attribute
    ("cloud", "own index attribute (not shared)",
     r"setIndex\(\s*new\s+THREE\.BufferAttribute\(\s*geo\.index\.array", 1),
    # height-above-terrain semantics: the shell rides r + (cloudR - 1.0)
    ("cloud", "cloud height above terrain", r"P\.cloudR\s*-\s*1\.0", 1),
    # GLSL ES 1.00 has no atan2 -- using it kills the whole fragment shader silently.
    # Assert the correct spelling positively: a bare "no atan2 anywhere in the deck"
    # check also hits the vendored three.min.js (31 hits) and can never pass.
    ("cloud", "GLSL longitude via atan(y,x)",
     r"float\s+lon\s*=\s*atan\(\s*vDir\.z\s*,\s*vDir\.x\s*\)", 1),
]

PLACEHOLDERS = ["/*__THREE__*/", "/*__DATA__*/", "/*__TIME__*/"]


def _decode(b64: str) -> list:
    import base64
    return [b / 255.0 for b in base64.b64decode(b64)]


def _rank(xs: list) -> list:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0          # ties share their mean rank
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def _spearman(a: list, b: list) -> float:
    ra, rb = _rank(a), _rank(b)
    n = len(ra)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((ra[i] - ma) ** 2 for i in range(n)) ** 0.5
    db = sum((rb[i] - mb) ** 2 for i in range(n)) ** 0.5
    return 0.0 if da * db == 0 else num / (da * db)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deck", default=ROOT / "out" / "sphere_timeline.html", type=Path)
    ap.add_argument("--max-bytes", default=DEFAULT_MAX, type=int)
    a = ap.parse_args(argv)

    if not a.deck.exists():
        print(f"missing {a.deck}; run sphere/pipeline/assemble_timeline.py first",
              file=sys.stderr)
        return 2
    text = a.deck.read_text(encoding="utf-8", errors="replace")
    size = a.deck.stat().st_size

    rows: list[tuple[str, str, str]] = []
    failures = 0

    def check(group: str, label: str, ok: bool, want: str, got: str) -> None:
        nonlocal failures
        failures += 0 if ok else 1
        rows.append((group, label, f"{want:>6s} {got:>8s}  {'ok' if ok else 'FAIL'}"))

    print(f"{a.deck}")
    print(f"  {size:,} bytes  ({size / 1024 / 1024:.2f} MB, budget {a.max_bytes:,})")
    print()

    for group, label, pattern, want in REQUIRED:
        hits = len(re.findall(pattern, text))
        # want == 0 means "must be absent" -- a >= test would pass trivially there
        ok = (hits == 0) if want == 0 else (hits >= want)
        check(group, label, ok, str(want), str(hits))

    # The formula lives at more than one site (vertex displacement and the
    # height helper), so the gate is "every site still says 0.5", not "there is
    # exactly one site". A rewritten constant is the failure worth catching.
    sites = re.findall(r"alpha\s*\*\s*\(\s*h\s*[-\u2212]\s*([0-9.]+)\s*\)", text)
    check("displace", "formula constant 0.5 at all sites",
          bool(sites) and all(s == "0.5" for s in sites),
          "0.5", f"{len(sites)} site" + ("" if len(sites) == 1 else "s"))

    for ph in PLACEHOLDERS:
        hits = text.count(ph)
        check("build", f"{ph} consumed", hits == 0, "0", str(hits))

    check("size", "deck under budget", size < a.max_bytes,
          f"<{a.max_bytes // 1024}K", f"{size // 1024}K")

    # --- data level: the cloud must stay a DIFFERENT reading of the field ---------
    # Cloud is link reach, not density. The measured field is anti-correlated with
    # height (~-0.44 on the real corpus); if a future change makes cloud a restatement
    # of the terrain the two layers stop meaning anything, and no pixel test would
    # catch it because the render would still look plausible.
    data_path = a.deck.parent / "web_data.json"
    if data_path.exists():
        import json
        dd = json.loads(data_path.read_text(encoding="utf-8"))
        hh = _decode(dd["h"])
        big, small = _decode(dd["cloud"]["big"]), _decode(dd["cloud"]["small"])
        cloud = [0.6 * big[i] + 0.4 * small[i] for i in range(len(big))]   # PDEF.bigWeight
        rho = _spearman(hh, cloud)
        check("cloud", "cloud vs land |spearman| < 0.6", abs(rho) < 0.6,
              "<0.6", f"{rho:+.3f}")
    else:
        check("cloud", "cloud vs land |spearman| < 0.6", False, "<0.6", "no data")

    width = max(len(r[1]) for r in rows) + 2
    print(f"  {'group':10s} {'check'.ljust(width)} {'want':>6s} {'hits':>8s}")
    print(f"  {'-' * 10} {'-' * width} {'-' * 6} {'-' * 8}")
    for group, label, got in rows:
        print(f"  {group:10s} {label.ljust(width)} {got}")
    print()

    if failures:
        print(f"FAIL  {failures} render check(s) failed in the built deck")
        return 1
    print("PASS  starfield, ocean, glow and snow line are in the deck; "
          "placeholders consumed; size within budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())