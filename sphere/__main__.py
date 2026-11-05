# -*- coding: utf-8 -*-
"""Command line entry:  python -m sphere demo | build | vendor

`demo` is the zero-dependency path: it synthesises a fake memory store, fetches the
two vendored browser libs, and runs the whole pipeline into ./out.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "sphere" / "pipeline"
VENDOR = ROOT / "vendor"
DATA = ROOT / "data" / "input"
OUT = ROOT / "out"

ASSETS = {
    "three.min.js": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js",
    "katex.min.js": "https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js",
    "katex.min.css": "https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css",
}

# (label, script) - order matters
STEPS = [
    ("PCA projection",      "probe.py"),
    ("height field",        "build_sphere.py"),
    ("globe render",        "render_sphere.py"),
    ("time frames",         "gen_time_frames.py"),
    ("frame sheet",         "render_frames.py"),
    ("pack web data",       "gen_web_data.py"),
    ("assemble deck",       "assemble_timeline.py"),
]


def ensure_vendor(force: bool = False) -> None:
    VENDOR.mkdir(parents=True, exist_ok=True)
    missing = []
    for name, url in ASSETS.items():
        dest = VENDOR / name
        if not force and dest.exists() and dest.stat().st_size > 1024:
            continue
        missing.append((name, url, dest))
    if not missing:
        print("vendor: already present")
        return
    for name, url, dest in missing:
        print(f"vendor: fetching {name} ...")
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read()
        except Exception as e:  # noqa: BLE001
            raise SystemExit(
                f"could not fetch {name} from {url}\n"
                f"  {e}\n"
                f"  -> download it manually into {VENDOR} and re-run."
            ) from e
        dest.write_bytes(data)
        print(f"vendor: {name} ({len(data)/1024:.0f} KB)")


def pipeline_env() -> dict:
    env = dict(os.environ)
    env["SPHERE_INPUT"] = str(DATA)
    env["SPHERE_OUT"] = str(OUT)
    # keep the child processes' stdout unbuffered so progress is visible
    env["PYTHONUNBUFFERED"] = "1"
    return env


def run_pipeline() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    env = pipeline_env()
    for label, script in STEPS:
        path = PIPELINE / script
        if not path.exists():
            raise SystemExit(f"missing pipeline step: {path}")
        print(f"  [{label}] {script}")
        proc = subprocess.run([sys.executable, str(path)], env=env)
        if proc.returncode != 0:
            raise SystemExit(f"step failed: {script} (exit {proc.returncode})")


def cmd_demo(a) -> int:
    from sphere.demo import generate

    print("1/3 synthesise a fake memory store")
    info = generate(DATA, units=a.units, dims=a.dims, links=a.links, days=a.days, seed=a.seed)
    print(f"    {info['units']} units x {info['dims']} dims · {info['links']} links · "
          f"{info['clusters']} clusters · {info['days']} days")

    print("2/3 vendored browser libs")
    ensure_vendor()

    print("3/3 pipeline")
    run_pipeline()

    globe = OUT / "sphere_bumpy_1024.png"
    deck = OUT / "sphere_timeline.html"
    print("\ndone.")
    if globe.exists():
        print(f"  globe : {globe}")
    if deck.exists():
        print(f"  deck  : {deck}")
        print("  open it in a browser — drag to rotate, slider to replay 25 days")
    return 0


def cmd_build(a) -> int:
    if not (DATA / "embeddings.tsv").exists():
        raise SystemExit(
            f"no input found at {DATA / 'embeddings.tsv'}\n"
            f"  -> put your own files there (see README), or run: python -m sphere demo")
    ensure_vendor()
    run_pipeline()
    print(f"\ndone. outputs in {OUT}")
    return 0


def cmd_vendor(a) -> int:
    ensure_vendor(force=a.force)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m sphere", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    d = sub.add_parser("demo", help="synthesise fake data and build the globe")
    d.add_argument("--units", default=3000, type=int)
    d.add_argument("--dims", default=64, type=int)
    d.add_argument("--links", default=6000, type=int)
    d.add_argument("--days", default=25, type=int)
    d.add_argument("--seed", default=20261105, type=int)
    d.set_defaults(func=cmd_demo)

    b = sub.add_parser("build", help="build from data/input/")
    b.set_defaults(func=cmd_build)

    v = sub.add_parser("vendor", help="fetch three.js + KaTeX into vendor/")
    v.add_argument("--force", action="store_true")
    v.set_defaults(func=cmd_vendor)

    a = ap.parse_args(argv)
    if not getattr(a, "func", None):
        ap.print_help()
        return 1
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())