"""Bilingual drift check: do the English and Chinese editions still say the same thing?

Markdown alone cannot keep two languages in sync, and a human diff cannot either
once the files are a screen apart. This script compares the *skeletons* that are
language independent, so prose can be translated freely while anything that must
not diverge is caught:

  headings       same count, same level sequence (captured by order)
  code blocks    same count, same language tag, same non-comment lines
  inline code    same identifier set (paths, commands, symbols, formulas)
  link targets   same set, ignoring the language-switcher links themselves
  numbers        same multiset of numeric literals (1,024 / 0.928 / 72 ...)
  tables         same row and column counts, in order
  length         character-count ratio inside a sane band, catching an edition
                 that was emptied out or half-translated

Deliberately NOT compared: prose, heading text, code comments (translated on
purpose, as long as the executable lines survive).

Usage
    python scripts/check_bilingual_sync.py             # check every pair
    python scripts/check_bilingual_sync.py --pair README.md README.zh-CN.md

Exit code 0 = in sync, 1 = drifted, 2 = a file is missing.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# English file -> Chinese file. Add a line here when a document gets translated.
DEFAULT_PAIRS = [
    ("README.md", "README.zh-CN.md"),
    ("CHANGELOG.md", "CHANGELOG.zh-CN.md"),
]

# The language switcher itself is expected to differ between the two editions.
SWITCHER_TARGETS = {
    "README.md", "README.zh-CN.md", "CHANGELOG.md", "CHANGELOG.zh-CN.md",
}

# Ratio of non-whitespace character counts, Chinese / English. Chinese packs more
# meaning per character, so the band is wide on purpose -- it exists to catch an
# edition that lost whole sections, not to nag about style.
LENGTH_RATIO_MIN = 0.15
LENGTH_RATIO_MAX = 1.10


def squeeze(s: str) -> str:
    return re.sub(r"\s+", "", s)


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    out: dict = {"path": path, "chars": len(squeeze(text))}

    out["headings"] = [len(m.group(1)) for m in re.finditer(r"^(#{1,6})\s+\S", text, re.M)]

    blocks = []
    for m in re.finditer(r"^```(\w*)\n(.*?)^```", text, re.M | re.S):
        lang, body = m.group(1), m.group(2)
        # Every non-blank line must match exactly, comments included. Code and
        # its comments stay in English in both editions; only prose is
        # translated. That keeps this rule blunt and unambiguous.
        keep = [re.sub(r"\s+", " ", line.strip()) for line in body.splitlines() if line.strip()]
        blocks.append((lang, tuple(keep)))
    out["blocks"] = blocks

    out["inline"] = sorted(set(m.group(1).strip() for m in re.finditer(r"`([^`\n]+)`", text)))

    targets = set()
    for m in re.finditer(r"\[[^\]]*\]\(([^)\s]+)\)", text):
        t = m.group(1)
        if t in SWITCHER_TARGETS:
            continue
        targets.add(t)
    out["links"] = sorted(targets)

    # numeric literals, keeping separators so 1,024 != 1024 stays visible
    out["numbers"] = sorted(re.findall(r"\d+(?:[.,]\d+)*", text))

    tables = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            cols = len([c for c in lines[i].strip().strip("|").split("|")])
            rows = 0
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows += 1
                j += 1
            tables.append((rows, cols))
            i = j
            continue
        i += 1
    out["tables"] = tables
    return out


def compare(en: dict, zh: dict) -> list[str]:
    problems = []

    if en["headings"] != zh["headings"]:
        problems.append(
            f"heading structure differs: en {en['headings']} vs zh {zh['headings']}")
    if [b[0] for b in en["blocks"]] != [b[0] for b in zh["blocks"]]:
        problems.append(
            f"code block language tags differ: en {[b[0] for b in en['blocks']]}"
            f" vs zh {[b[0] for b in zh['blocks']]}")
    else:
        for idx, (be, bz) in enumerate(zip(en["blocks"], zh["blocks"])):
            if be[1] != bz[1]:
                only_en = [l for l in be[1] if l not in bz[1]]
                only_zh = [l for l in bz[1] if l not in be[1]]
                problems.append(
                    f"code block #{idx + 1} ({be[0]}) executable lines differ;"
                    f" only-en={only_en[:3]} only-zh={only_zh[:3]}")

    if en["inline"] != zh["inline"]:
        only_en = [x for x in en["inline"] if x not in zh["inline"]]
        only_zh = [x for x in zh["inline"] if x not in en["inline"]]
        problems.append(f"inline code differs; only-en={only_en} only-zh={only_zh}")

    if en["links"] != zh["links"]:
        only_en = [x for x in en["links"] if x not in zh["links"]]
        only_zh = [x for x in zh["links"] if x not in en["links"]]
        problems.append(f"link targets differ; only-en={only_en} only-zh={only_zh}")

    if en["numbers"] != zh["numbers"]:
        ce, cz = Counter(en["numbers"]), Counter(zh["numbers"])
        only_en = sorted((ce - cz).elements())
        only_zh = sorted((cz - ce).elements())
        problems.append(f"numeric literals differ; only-en={only_en} only-zh={only_zh}")

    if en["tables"] != zh["tables"]:
        problems.append(f"table geometry differs: en {en['tables']} vs zh {zh['tables']}")

    ratio = zh["chars"] / max(en["chars"], 1)
    if not (LENGTH_RATIO_MIN <= ratio <= LENGTH_RATIO_MAX):
        problems.append(
            f"length ratio {ratio:.2f} outside [{LENGTH_RATIO_MIN}, {LENGTH_RATIO_MAX}]"
            f" (en {en['chars']} chars, zh {zh['chars']} chars)")

    return problems


def check_pair(en_path: Path, zh_path: Path) -> bool:
    missing = [p for p in (en_path, zh_path) if not p.exists()]
    if missing:
        print(f"MISSING: {', '.join(str(m) for m in missing)}", file=sys.stderr)
        return False
    en, zh = parse(en_path), parse(zh_path)
    problems = compare(en, zh)
    print(f"{en_path}  <->  {zh_path}")
    print(f"  headings {len(en['headings'])}/{len(zh['headings'])}"
          f"  blocks {len(en['blocks'])}/{len(zh['blocks'])}"
          f"  inline {len(en['inline'])}/{len(zh['inline'])}"
          f"  links {len(en['links'])}/{len(zh['links'])}"
          f"  numbers {len(en['numbers'])}/{len(zh['numbers'])}"
          f"  tables {len(en['tables'])}/{len(zh['tables'])}"
          f"  chars {en['chars']}/{zh['chars']}")
    if not problems:
        print("  IN SYNC")
        return True
    for p in problems:
        print(f"  DRIFT  {p}")
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pair", nargs=2, metavar=("EN", "ZH"),
                    help="check a single pair instead of the defaults")
    ap.add_argument("--root", default=ROOT, type=Path)
    a = ap.parse_args(argv)

    pairs = [tuple(a.pair)] if a.pair else DEFAULT_PAIRS
    ok = True
    for en_rel, zh_rel in pairs:
        ok &= check_pair(a.root / en_rel, a.root / zh_rel)
        print()
    if ok:
        print("PASS  every bilingual pair is in sync")
        return 0
    print("FAIL  the editions have drifted; fix before tagging a release")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())