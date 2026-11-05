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
]

PLACEHOLDERS = ["/*__THREE__*/", "/*__DATA__*/", "/*__TIME__*/"]


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
        check(group, label, hits >= want, str(want), str(hits))

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