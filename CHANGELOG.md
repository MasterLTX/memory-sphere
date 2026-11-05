# Changelog

**English** · [简体中文](CHANGELOG.zh-CN.md)

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.1] — 2026-11-05

### Fixed

- **The hero animation spun about the wrong axis.** The render matrix was
  `M = rmat_x(radians(72)) @ rmat_y(angle)`. Since `Rx(t)` maps the spin axis
  `ŷ` to `(0, cos t, sin t)`, that put **95% of the axis along +z — straight
  down the view direction** — so the globe rotated *in the image plane* like a
  plate instead of turning like a planet. Now `rmat_x(radians(-18))`: 95% of the
  axis stays vertical, and the tilt matches the viewpoint already used by
  `render_sphere.py` and `render_frames.py`, so the poles sit on the same side
  in every render the project produces.
- Comment and value had disagreed: the comment said "tilted 18 deg", the code
  passed 72 (i.e. 90 − 18, counted twice).
- `README.md` linked `docs/formulas.md`, which never existed in the repository.
  The reference now points at `sphere/pipeline/build_sphere.py`, where the
  arithmetic actually lives.
- `docs/index.html` — the GitHub Pages deck — hard-coded `10,441`, `1020` and
  `0.709` as static placeholders while the data embedded in the page is the
  3,000-memory demo. Before its JavaScript ran, the page asserted real-data
  numbers it was not showing; scrapers, link previews and anyone with JS off saw
  them too. The placeholders are now `—` and the page carries a static line
  saying it renders synthetic data.
- Both READMEs described `docs/` as holding `formulas, architecture, pitfalls`.
  None of those files exist in `docs/`.

### Added

- `scripts/check_hero_spin.py` — decides **from pixels** whether the hero GIF
  spins about the vertical axis or in the image plane, by fitting a rotation
  model and a translation model to consecutive frames and comparing residuals.
  Exit code 1 on regression, so it can gate a release.
- `README.zh-CN.md` and `CHANGELOG.zh-CN.md` — full Simplified Chinese editions,
  linked from a language switcher at the top of both English files.
- `scripts/check_bilingual_sync.py` — machine check that the two language
  editions have not drifted apart: it compares heading structure, code blocks,
  link targets, numeric literals, table geometry and length ratio, and exits 1
  when any of them disagree.
- `CHANGELOG.md` (this file).
- `python -m sphere --version`, backed by a single `__version__` in
  `sphere/__init__.py`. `scripts/check_version_sync.py` fails a release when the
  code version, the newest CHANGELOG entry (both languages) and the git tag at
  HEAD disagree.
- README gained a "what this globe can and cannot answer" section, because the
  honest reading of the PCA-vs-UMAP argument is that a sphere position carries
  almost no semantic proximity. Measured: top-10 neighbour retention from the
  original 64-D space to the sphere is 1.40% against a 0.36% random baseline,
  and mean cosine similarity inside one anchor is 0.0680 versus −0.0004 across
  anchors. The globe is a density and activity dashboard, not a retrieval
  surface.
- README now separates the two kinds of acceptance testing: visual properties
  get a pixel test, functional properties get a task test.
- `requirements.txt` states the Python floor (3.9). All three gates resolve the
  repository root from their own location, so they run from any working
  directory instead of silently failing somewhere else.

### Measured

Residual fit over consecutive frame pairs of `examples/rotating.gif`
(lower translation residual + near-zero vertical drift = planet spin):

| build | translation / rotation | fitted motion | vertical drift |
|---|---|---|---|
| 1.0.0 | 1.463 | +9.09 deg/frame about the centre (the intended rate is 10 deg/frame, one turn in 36 frames) | 0.750 |
| 1.0.1 | 0.456 | dx +22.1 px/frame, dy −0.3 px | 0.012 |

Run `python scripts/check_hero_spin.py examples/rotating.gif` to reproduce.

## [1.0.0] — 2026-11-05

First public release.

### Added

- Pipeline: PCA → 1,024 equal-area sphere anchors → density / PageRank / entity
  count / recency / type aggregated into a height field → displaced icosphere.
- `python -m sphere demo` — synthesises 3,000 fake memories so the whole
  pipeline runs with no database, no API key and no network.
- Inspectable deck with a 25-frame time slider, six height-field views and
  contour lines.
- De-identified input contract (`embeddings.tsv`, `links.tsv`, `ent_count.tsv`,
  `models.tsv`) plus a read-only Hindsight exporter under `adapters/`.
- GitHub Pages demo, MIT licence, third-party notices.

### Known issues

- The committed `examples/rotating.gif` spins about the view axis (plate spin)
  rather than the vertical one. Source archives of this tag therefore contain
  that GIF. Fixed in 1.0.1; the tag is intentionally left untouched.