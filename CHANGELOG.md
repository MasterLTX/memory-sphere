# Changelog

**English** · [简体中文](CHANGELOG.zh-CN.md)

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.2.0] — 2026-11-06

### Added

- **A cloud layer that means something.** `sphere/pipeline/build_cloud.py` derives a
  32×32 field from **link reach**: for each cell, the mean great-circle distance from
  its memories to their own top-5 true neighbours. Thick cloud marks *isolation* — the
  memories gathered there keep their real neighbours far away — not density, which
  correlates with the memory count at +0.998 and is therefore already the terrain.
  Against the height field it is a different reading rather than a restatement:
  spearman −0.46 on the real corpus, −0.24 on the demo.
- **13 live render parameters.** Cloud height, coverage, big-vs-small weight,
  cloud scale, drift rate, opacity, terrain relief, snow line, waterline, water
  opacity, crest glow, star brightness and star density. Every knob is a slider, it
  persists to localStorage, and it is written into the URL, so a look can be shared
  as a link.
- `check_render.py` now gates the cloud: the material, both field textures, its own
  index attribute, height-above-terrain semantics and the GLSL `atan(y, x)` spelling,
  plus a data-level assertion that the cloud stays a *different* reading of the field
  (|spearman| < 0.6).

### Changed

- **The cloud is a shaded shell, not a sprite field.** The first implementation floated
  ~10k point sprites at a fixed radius 1.30. That produced two silhouettes — a cloud
  ball with a small planet inside it — and it could not make cloud texture at any
  setting of size, alpha or count: stacked sprites only ever read as even grey fog.
  The shell now rides the terrain's own vertices at a fixed height above it, so there
  is exactly one silhouette, and its look is a fragment shader: the 32×32 field says
  *where*, domain-warped fbm says *how torn*, and a smoothstep gives each bank an edge.
  Weather drifts by sliding the field lookup along longitude instead of spinning the
  geometry.
- **`cloudR` changed meaning** — it was the shell's radius, it is now its height above
  the terrain (range 1.00–1.40 reads as 0.00–0.40 above the surface). Saved looks move
  to a new storage key, so a stale 1.32 cannot float the weather overhead.
- **Coverage is a property of the render, not of the corpus.** The field is stretched
  to its own 5–95 percentile and the threshold comes from that field's quantiles, so
  "density" keeps meaning "share of sky" on any dataset. A fixed threshold painted
  ~40% of the sphere on the real corpus and ~85% on the demo.

### Fixed

- Two failures that do not throw, both of which silently drew nothing: `atan2` is not
  GLSL ES 1.00 (the two-argument form is `atan(y, x)`), and handing one geometry's
  index *attribute* to a second geometry makes the two fight over a VAO binding.

## [1.1.0] — 2026-11-05

### Added

- **Search and locate one memory.** `sphere/pipeline/build_index.py` exports `idbin`
  — every memory's anchor — so the deck can answer "where is this one", which
  1.0.1's boundary table listed as something the globe could not do.
- **True-neighbour jump.** The same index ships `knn`: each memory's top-5
  neighbours in the **original** vector space, not on the sphere. A memory's
  anchor is not its neighbourhood, and this jump is what shows the difference.
- **Named ridges and trenches.** 39 regions on the demo (21 ridges, 18 trenches),
  all 39 labelled from their own word statistics; 6/6 of the demo's known themes
  recovered, mean lift 3.50x over a size-matched random draw.
- **Render additions:** a three-tier starfield (14 bright / 210 mid / the rest
  faint), an ocean `THREE.ShaderMaterial` at a data-relative waterline, a crest
  glow shell, and a snow-line palette band above the eight original colour stops.
- `scripts/check_search.py` and `scripts/check_render.py` — one gate for the
  lookup index, one for the built deck, both exit 0/1/2 and both runnable from
  any working directory.

### Changed

- **The README no longer says a sphere position carries no semantic proximity.**
  1.0.1 wrote "does not carry semantic proximity", which was too absolute.
  Measured on the demo: top-10 neighbour retention is 1.40% against 0.33% at
  random (4.2x), true top-5 neighbours share the memory's own anchor 0.58% of the
  time against 0.10% (5.9x), and true neighbours sit a median 0.272 of a
  half-circle away against 0.501 (1.8x closer). The sphere carries a weak but
  real signal.
- **"Neighbours are usually on the other side of the globe" is NOT supported.**
  Only 15.3% of true neighbours are beyond half a globe, against 50.2% for random
  pairs. `scripts/measure_proximity.py` now computes and prints both rows, so the
  claim and the measurement cannot separate again.
- One line that puts the two together: true neighbours **almost always change
  anchor (99.4%)** and yet usually do **not** cross the globe (median 0.272, only
  15.3% beyond half a globe).
- Both READMEs' boundary table moved one row: the globe **can** say where one
  specific memory sits (the lookup index), and still cannot rank results by
  sphere adjacency.

### Design

- **A region label is always printed with its own statistic**, never bare:
  `auth · 57.3% 的记忆含该词（随机 16.5%）`. A bare label would read as "this hill
  is the auth topic", which is precisely what the README's boundary section says
  the globe cannot tell you. Label and number travel together.
- **The longitude wrap is part of the spec, not an edge case**: column 31 touches
  column 0. A ridge across the antimeridian is one region; `check_regions.py`
  fails the build when the flood fill splits it into two.

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