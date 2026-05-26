# New Hampshire Township Map & Stickers — Design

**Date:** 2026-05-25
**Status:** Approved (brainstorming) — pending implementation plan

## Summary

A two-part collectible product:

1. **A large base map of New Hampshire** (24×36 in poster) showing a thick state
   outline, medium county outlines, thin township outlines, and township names.
   Every township is an empty "slot."
2. **One die-cut sticker per township** (~259 files, all county subdivisions),
   each cut to that town's true boundary shape at the *same scale as the base
   map*, so it drops into its slot like a puzzle piece. Each sticker is an
   editable SVG with a clearly-named, empty `artwork` group where unique
   per-town art is added later.

The collector peels a sticker and places it on the map as they visit each town.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Boundary data source | US Census TIGER/Line (`tl_2023_33_cousub`) |
| Editing software | Unknown → generic, spec-compliant SVG with clearly-named groups |
| Sticker output | One editable SVG file per township |
| Sticker fit | True-scale die-cut (puzzle fit) — identical scale to base map |
| Base map size | Large poster, 24×36 in |
| Artwork placement | Empty `artwork` group, centered on the shape |
| Town set | All ~259 county subdivisions (incl. unincorporated grants/locations) |
| Architecture | Approach A — dedicated `townships` subpackage, geopandas isolated to data layer |

## Architecture (Approach A)

A new `lake_sticker/townships/` subpackage. geopandas / CRS work is confined to
the data layer; rendering consumes plain coordinate lists, matching the existing
`lake_sticker/map/render.py` pattern (dependency-light, easily unit-tested).

```
lake_sticker/townships/
  __init__.py
  tiger.py        # download + cache TIGER shapefile; build projected feature set
  projection.py   # CRS reprojection + the single shared meters→SVG transform
  basemap.py      # render the 24x36 poster (state + county + township + names)
  sticker.py      # render one die-cut township sticker
  cli.py          # `nh-map` command: fetch once, emit poster + all stickers
tests/
  test_townships_tiger.py
  test_townships_projection.py
  test_townships_basemap.py
  test_townships_sticker.py
```

Packaging:
- New console script `nh-map = lake_sticker.townships.cli:main` in `pyproject.toml`.
- New optional extra `townships = ["geopandas", "shapely", "requests", "pyproj"]`.

## Component design

### Data layer — `tiger.py`

- Download `tl_2023_33_cousub.zip` (NH county subdivisions, FIPS 33) from the
  Census TIGER HTTPS endpoint into the existing `.cache/` folder. Cache once,
  reuse on subsequent runs (same pattern as `map/fetch.py`).
- geopandas reads the shapefile → ~259 county-subdivision polygons. Each carries
  `NAME` and `COUNTYFP`.
- **County boundaries** are derived by dissolving subdivisions on `COUNTYFP`.
  **State outline** is derived by dissolving everything. One download yields all
  three tiers.
- 10 NH county names come from a hardcoded `COUNTYFP → name` map.
- Output: plain Python structure — a list of township records
  `{name, county, geometry}` plus the dissolved county geometries (with names)
  and the dissolved state geometry. No geopandas needed downstream.

### Projection — `projection.py`

- Reproject from TIGER's CRS (EPSG:4269, lat/lon) to a planar CRS in meters —
  **NH State Plane, EPSG:32110** by default (UTM 19N / EPSG:32619 as fallback) —
  so shapes are geometrically true with no latitude stretch.
- Compute **one** transform from the whole-state projected bounds:
  - a single `scale` (SVG units per meter), sized so the state fills the
    poster's printable area;
  - a y-axis flip (SVG y grows downward).
  This `scale` is the shared constant that guarantees puzzle-fit.
- Helpers:
  - `project_for_basemap(geom)` — applies `scale` + the poster-wide translate.
  - `project_for_sticker(geom)` — applies the **same** `scale` but a translate
    that recenters on the town's own bounds.
- Poster sizing: 24×36 in at 96 units/in → 2304×3456 viewBox, with
  `width="24in" height="36in"` so it prints at true physical size.

### Base-map renderer — `basemap.py`

Layered SVG, painted back-to-front (mirrors `map/render.py` structure):

- `<g id="townships">` — each subdivision as a thin-stroke outline, no fill.
- `<g id="counties">` — dissolved county outlines, medium stroke.
- `<g id="state">` — state outline, thick stroke.
- `<g id="labels">` — town name at each polygon's label point
  (shapely `representative_point()`, which stays inside concave shapes).
  Font auto-shrinks for small polygons; towns too small for a readable label get
  a small number keyed to a printed legend block in the poster margin.
- `<g id="title">` — "NEW HAMPSHIRE" title, reusing the existing serif title style.

### Sticker renderer — `sticker.py`

One SVG per subdivision, scaled identically to the base map:

- `<g id="cut">` — town boundary as the die-cut path, with a small outward buffer
  (≈0.08 in, computed in projected meters then scaled) for a printable
  kiss-cut white border.
- `<g id="boundary">` — town outline drawn just inside the cut.
- `<g id="label">` — town name.
- `<g id="artwork">` — **empty**, centered on the shape's label point, with a
  comment marking where to drop unique art.
- viewBox tightly fit to the buffered shape so each file is self-contained.

### CLI & file naming — `cli.py`

`nh-map [--out-dir DIR] [--no-stickers] [--basemap-only]`:

- Fetches/caches TIGER once.
- Writes `nh_basemap.svg`.
- Writes `stickers/<County>/<Town>.svg` — names sanitized to safe filenames
  (lowercased, spaces→underscores, punctuation stripped) and grouped into
  per-county subfolders to organize ~259 files and disambiguate repeated names
  across counties.

## Testing

- `test_townships_tiger.py` — classification/dissolve logic against a small
  fixture of fake subdivision records (no network); county/state derivation,
  county-name mapping.
- `test_townships_projection.py` — the core guarantee: a geometry projected for
  the base map and for its sticker uses the **same scale**; round-trip a known
  box and assert dimensions match within tolerance.
- `test_townships_basemap.py` — output is well-formed SVG with the expected
  layer groups and correct poster dimensions; labels present.
- `test_townships_sticker.py` — output has `cut`, `boundary`, `label`, and an
  empty `artwork` group; viewBox fits the buffered shape; buffer applied.

Network/geopandas-heavy paths are exercised against cached fixtures, not live
downloads, keeping the suite offline and fast (matching `test_map_fetch.py`).

## Out of scope (YAGNI)

- The actual per-town artwork (the product is the *editable slot* for it).
- Other states (NH only; the FIPS code and CRS are parameterizable later if needed).
- Print-shop bleed/registration marks beyond the kiss-cut buffer.
- Automated nesting/packing of stickers onto shared cut sheets (one file per town).
