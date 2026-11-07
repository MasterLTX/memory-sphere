# memory-sphere

**English** · [简体中文](README.zh-CN.md)

> **Memory Sphere**
>
> Every memory is a mote of dust; given time, it settles into terrain.
>
> Memory is more than 1,024-dimensional vectors. It is also a planet that grows, slowly. Every memory lands; where many settle close together a ridge rises; what is forgotten becomes a trench, waiting to be remembered. Turn the globe, and what you see is not data — it is how a system remembers, how it forgets, and how it grows a shape in time.

![rotating globe](examples/rotating.gif)

*(36 frames, 3.6 s per turn, rendered offline from the same pipeline — no screen recorder, no private data)*

**[▶ Live demo — drag the globe](https://masterltx.github.io/memory-sphere/)** (3,000 **synthetic** memories at **64** dims, there to prove the pipeline runs; it demonstrates nothing about the 1,024-dim real data below)

## What it actually does

In one line: 10,441 real memories, 1,024 dims each → PCA keeps the first 3 → land on 1,024 **equal-area** sphere anchors → aggregate density, PageRank, entity count, recency and type into a height field → displaced icosphere, plus a 25-frame time slider.

Most vector visualisations give you a dot cloud: 10k points, no structure you can point at.
This one **aggregates first, then draws**:

| stage | what happens |
|---|---|
| 1. preprocess | centre on the mean, L2-normalise |
| 2. reduce | covariance eigen-decomposition, 1024 → 50 → first 3 (≈0.3 s) |
| 3. sphere | normalise the 3D coordinates onto S² |
| 4. bin | 32×32 **equal-area** lat/lon grid — 1,024 anchors, each π/256 of the sphere |
| 5. aggregate | per anchor: count, mean PageRank, mean entity count, recency, type weight |
| 6. height | weighted **rank**-normalised sum → `h ∈ [0,1]` |
| 7. smooth | seam-aware separable Gaussian + band-pass for the hills |
| 8. displace | `R = 1 + α(h − 0.5)`, α = 0.28 |
| 9. render | icosphere (no polar singularity), normals from the **displaced** geometry |

Why PCA instead of UMAP: because this project draws terrain, not neighbourhoods.

The top-3 singular values sit close together (61.3 / 58.7 / 56.9, ratio 0.928), so the projection
has no single dominant direction. Points land roughly evenly on the sphere — 1,020 of 1,024 bins
populated, centroid offset 0.058 — and the surface reads as a continuous landscape rather than a
handful of clumps. PCA is also deterministic: the same input always produces the same globe, which
UMAP and t-SNE do not promise.

The price is locality, and the next section measures it. If what you want is neighbourhoods
preserved, that is a different projection with a different look, and it is not this project.

See [`sphere/pipeline/build_sphere.py`](sphere/pipeline/build_sphere.py) for the exact arithmetic.

Those real-data numbers come from the author's own 10,441-memory store, which is not part of
this repository. What you can reproduce here is the next section's set, computed on the demo data.

## The cloud is a second reading, not decoration

A shell above the terrain carries a second field, and it is measured rather than drawn for looks.
Cloud thickness is **link reach**: for each anchor, the mean great-circle distance from its memories
to their own top-5 true neighbours. So a thick bank marks *isolation* — the memories gathered there
keep their real neighbours on the far side of the sphere — and a thin patch marks a cluster whose
neighbours sit right next to it.

Two candidate definitions were measured against the memory count and the height field before either
was drawn:

| definition | vs memory count | vs height field | verdict |
|---|---|---|---|
| number of links | **+0.998** | +0.057 | rejected — that is just density again |
| link distance (reach) | −0.395 (real) / −0.211 (demo) | **−0.440** (real) / −0.235 (demo) | kept |

The second row is why the cloud is worth having: it is anti-correlated with the terrain, so the two
layers are complementary readings of the same memories rather than one painted twice.

Every render parameter is live: thirteen sliders (cloud height, coverage, big-vs-small weight, cloud
scale, drift, opacity, terrain relief, snow line, waterline, water opacity, crest glow, star
brightness, star density) write to localStorage **and** into the URL, so a look you like is a link
you can share.

## What this globe can and cannot answer

This section is discipline, not a disclaimer — it decides when you should open it.

A position on this sphere carries **a weak but real proximity signal, and far too little of it
to retrieve with**. It is not a semantic map: two memories that mean similar things are
*more likely than chance* to land close together — 1.8x to 5.9x more likely, depending on the
test — but the absolute rates stay in the low single digits, so "close together" on this globe
is not evidence that two memories are about the same thing.

The absolute version of this — "a sphere position does not carry semantic proximity" — is wrong
on both counts, and the numbers below say why: the signal exists, and a memory's neighbours do
**not** usually sit on the other side of the globe. Only 15.3% of true neighbours are more than
half a globe away, against 50.2% for random pairs.

Measured on the 3,000-by-64 synthetic set, recomputed through this project's own pipeline:

| test | result | reference |
|---|---|---|
| variance carried by the top 3 PCs | 7.7% | ≈10% on real data |
| singular-value ratio (closer to 1 = more isotropic) | 0.906 | 0.928 on real data |
| sphere centroid offset | 0.006 | 0.058 on real data |
| top-10 neighbour retention, original 64-D → sphere | **1.40%** | random baseline 0.33% |
| top-5 true neighbours sharing the memory's own anchor | **0.58%** | random baseline 0.10% (1/1,024) |
| great-circle distance, memory → its true neighbours (median; half-circle = 1) | **0.272** | random median 0.501 |
| share of those neighbours beyond half a globe | **15.3%** | random 50.2% |
| mean cosine similarity inside one anchor | 0.0680 | −0.0004 across anchors |

Three lifts, one reading: top-10 retention is 1.40% against a 0.33% random baseline — the chance
that two unrelated 10-sets overlap — a 4.2x lift; a memory's true top-5 neighbours share its own
anchor 0.58% of the time against 0.10%, a 5.9x lift; and they sit a median 0.272 of a
half-circle away against 0.501 at random, 1.8x closer. **The direction is right and the signal
is real; it is still far too weak to retrieve with.** Ask for "something like this one" and the
original vector space answers with a cosine near 0.9; sphere adjacency answers with a 1.40% hit
rate.

The two facts that decide how to read this: a memory's true neighbours almost always change
anchor (99.4% of them do), and yet they usually do **not** cross the globe — median 0.272, only
15.3% beyond half a globe. The anchor is not the neighbourhood, and it is not a coin flip either.

The three new rows use the lookup index's own neighbours, so this table and the shipped
"true neighbours" jump cannot drift apart. Reproduce every row with
`python scripts/measure_proximity.py`.

So the boundary is clean:

| it can answer | it cannot answer |
|---|---|
| where memories are dense | why these two memories are related |
| where they are active (high PageRank) | why this memory was recalled by that query |
| which region new memories land in, and where one specific memory sits | how to rank search results by sphere adjacency (a 5.9x lift is not a ranking) |
| how density migrates over time (25-frame slider) | what a ridge means on its own — its name is a word count, never a topic |

One line: **this is a health dashboard for a memory system, not a search entrance.**

A hill means "this patch of the sphere holds many memories with high count / PageRank /
entity count" — not "this patch is one semantic topic".

A named ridge is not an exception to that. From 1.1.0 every region label is printed with the
statistic that earns it (`auth · 57.3% 的记忆含该词（随机 16.5%）`), never on its own, because a
bare label would read as a topic and contradict this section.

## Quick start

```bash
git clone https://github.com/MasterLTX/memory-sphere
cd memory-sphere
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m sphere --version   # -> memory-sphere 1.2.0 (tag v1.2.0)
python -m sphere demo        # synthesises 3,000 fake memories, builds the globe
open out/sphere_timeline.html
```

No database, no API key, no network (except the first run, which fetches `three.js` + `KaTeX`
into `vendor/`).

The demo runs 3,000 by 64 for speed. In the table above, the *result* column is measured on
that synthetic set; the *reference* column comes from the real 10,441 by 1,024 data.

## Use your own memory

Drop four files into `data/input/` — only the first is required:

| file | format |
|---|---|
| `embeddings.tsv` | `id <tab> type <tab> date <tab> [v1,v2,…,vn]` |
| `links.tsv` | `src <tab> dst <tab> weight <tab> kind` |
| `ent_count.tsv` | `unit_id <tab> count` |
| `models.tsv` | `name <tab> [v1,v2,…,vn]` |

With only `embeddings.tsv` the pipeline degrades to a pure-density globe instead of failing.
If you use Hindsight as your memory store, `adapters/hindsight_export.sql`
dumps those files (read-only, no writes).

## Layout

```
sphere/pipeline/   the original flat scripts (being folded into a package)
adapters/          exporters that produce the four input files
docs/              publishing walkthrough, Pages deck
examples/          committed demo output
scripts/           release gates: hero spin, bilingual drift, version sync, index, deck
```

## Pitfalls already paid for

1. **Lat/lon mesh rendering** — poles degenerate into a radial starburst. Use icosphere for
   drawing, keep the lat/lon grid for *statistics only*.
2. **`IcosahedronGeometry(1, 5)` is not 5-level recursive subdivision** — it is
   `20 × (detail+1)²` faces, i.e. 720. Use `detail=31` for 20,480.
3. **`PolyhedronGeometry` is non-indexed** — `computeVertexNormals()` gives flat shading until
   you weld vertices by position.
4. **Normals must come from the displaced geometry**, not the sphere direction, or the front
   face shows no hills at all.
5. **CSS class collisions** — `querySelectorAll('.btn')` silently bound a second handler to a
   toggle button, writing `undefined` into the field selector and killing the render before the
   colour loop ran. Scope selectors with a data attribute.
6. **A spin can be wrong and still look like motion.** `Rx(t)` sends the spin axis `ŷ` to
   `(0, cos t, sin t)`; at `t = 72°` that is 95% along `+z` — the view direction — so the globe
   rotates *in the image plane* like a plate instead of turning like a planet. Four still frames
   side by side look convincing either way. Decide from pixels, not eyes:
   `python scripts/check_hero_spin.py` fits a rotation model and a translation model to
   consecutive frames and fails if the rotation one wins.

One more rule about acceptance testing, because mixing the two judges has burned this project:
a **visual** property (spin direction, palette, star flare) deserves a pixel test — that is what
`check_hero_spin.py` is; a **functional** property (click a hill, do you get that region's
memories) deserves a task test — pose a concrete question and see whether the thing answers it.
Both have failed here: judging a visual bug by "it looks fine" gives you "pretty therefore
correct", and judging a function by pixel comparison gives you "the screenshot matches
therefore it works".

## License

MIT. Bundled at build time: three.js (MIT), KaTeX (MIT) — see `THIRD_PARTY_NOTICES.md`.