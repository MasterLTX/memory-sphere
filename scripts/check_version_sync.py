"""Version consistency gate: three places must agree before a release ships.

A version number wants to live in exactly one place, but a repository always
ends up with several copies of it, and they drift silently:

    sphere/__init__.py     __version__            <- the single source of truth
    CHANGELOG.md           newest `## [x.y.z]`    <- what the release says
    CHANGELOG.zh-CN.md     newest `## [x.y.z]`    <- must match, it is a translation
    git tag                a v* tag pointing at HEAD, if one was created

This script reads all four and fails when they disagree. Run it before tagging;
run it after tagging too, because a perfectly consistent tree with the wrong tag
name is still a wrong release.

Usage
    python scripts/check_version_sync.py            # full check, including the tag
    python scripts/check_version_sync.py --no-tag   # mid-development, tag not made yet

Exit code 0 = consistent, 1 = mismatch, 2 = a required file is missing.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.M)
# `## [1.0.1] — date`  /  `## [1.0.1] - date`; `[Unreleased]` is not a version
CHANGELOG_RE = re.compile(r"^##\s+\[(\d+\.\d+\.\d+)\]", re.M)


def read_py_version(path: Path) -> str | None:
    if not path.exists():
        return None
    m = VERSION_RE.search(path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def read_changelog_version(path: Path) -> str | None:
    if not path.exists():
        return None
    m = CHANGELOG_RE.search(path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def tags_at_head(root: Path) -> tuple[list[str], str | None]:
    """Tags pointing at HEAD *of the repo at root*.

    Returns (tags, problem). problem is None when git answered; otherwise it says
    why it could not, so 'no tag yet' and 'cannot query git' stay distinguishable
    -- silently passing the tag half of a release gate is how a wrong tag ships.
    """
    try:
        out = subprocess.run(["git", "tag", "--points-at", "HEAD"],
                             cwd=str(root), capture_output=True, text=True,
                             encoding="utf-8")
    except (OSError, subprocess.SubprocessError) as e:
        return [], f"cannot run git: {e}"
    if out.returncode != 0:
        return [], f"git failed here (not a repository?): {out.stderr.strip()[:120]}"
    return [x.strip() for x in out.stdout.splitlines() if x.strip()], None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=ROOT, type=Path)
    ap.add_argument("--no-tag", action="store_true",
                    help="skip the git tag check (use while developing)")
    a = ap.parse_args(argv)

    py = read_py_version(a.root / "sphere" / "__init__.py")
    en = read_changelog_version(a.root / "CHANGELOG.md")
    zh = read_changelog_version(a.root / "CHANGELOG.zh-CN.md")

    print("version in sphere/__init__.py   :", py or "MISSING")
    print("newest entry in CHANGELOG.md    :", en or "MISSING")
    print("newest entry in CHANGELOG.zh-CN :", zh or "MISSING")

    if py is None or en is None or zh is None:
        print("\nFAIL  a version source is missing", file=sys.stderr)
        return 2

    problems = []
    if not (py == en == zh):
        problems.append(f"code says {py}, CHANGELOG.md says {en}, CHANGELOG.zh-CN.md says {zh}")

    expected_tag = f"v{py}"
    if not a.no_tag:
        tags, problem = tags_at_head(a.root)
        if problem:
            print(f"\nFAIL  cannot verify the tag: {problem}", file=sys.stderr)
            return 2
        vtags = [t for t in tags if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
        if vtags:
            print(f"v* tag(s) pointing at HEAD     : {', '.join(sorted(vtags))}")
            wrong = [t for t in vtags if t != expected_tag]
            if wrong:
                problems.append(
                    f"tag {', '.join(wrong)} points at HEAD but the code says {py}"
                    f" (expected {expected_tag})")
        else:
            print(f"v* tag pointing at HEAD        : none"
                  f"  (release tag would be {expected_tag})")

    print()
    if not problems:
        print(f"PASS  everything agrees on {py}")
        return 0
    for p in problems:
        print(f"  MISMATCH  {p}")
    print("\nFAIL  version sources disagree; fix before tagging a release")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
