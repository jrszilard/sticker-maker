# Sticker Maker

Generate print-ready sticker SVGs from open geographic data. The toolkit produces
two related product families:

1. **Lake & map stickers** (`lake-sticker`) — an interactive CLI that turns a single
   place into a sticker: a lake's shoreline, or a small town/neighborhood map with
   roads, water, green spaces, buildings, and labeled points of interest.
2. **New Hampshire township map & stickers** (`nh-map`) — a 24×36 in NH base-map
   poster plus one true-scale, die-cut sticker per township. Each sticker is cut to
   the town's real boundary at the **same scale as the poster**, so it drops into its
   slot like a puzzle piece — peel and place as you visit each town.

Every sticker is emitted as **two SVGs**: a layered *editable* file (for finishing in
Inkscape / Illustrator) and a single-path *cut* file (for a vinyl cutter).

---

## Requirements

- Python 3.10+
- An internet connection on first run (data is fetched from OpenStreetMap / the US
  Census and cached locally under `.cache/`)

## Installation

```bash
# Base install — covers the lake & map stickers (lake-sticker)
pip install -e .

# Add the New Hampshire township map (nh-map): geopandas + pyproj
pip install -e ".[townships]"

# Optional: osmnx fallback for geometry fetching
pip install -e ".[osmnx]"

# Development (tests)
pip install -e ".[dev]"
```

This installs two console commands: `lake-sticker` and `nh-map`.

---

## Usage

### Lake & map stickers — `lake-sticker`

An interactive prompt. Run it and choose a mode:

```bash
lake-sticker
```

**Mode 1 — Lake sticker**
1. Search for a lake by name (add a state to narrow results, e.g. `Crystal Lake, NH`).
2. Configure the label/subtitle, border style (dotted ring, double-line frame, dashed
   ring, or none), shoreline simplification (auto by default), and colors.
3. Two files are written to `output/`:
   - `<lake>_editable.svg` — separate layers (shoreline, islands, label, border)
   - `<lake>_cut.svg` — single path, vinyl-ready

**Mode 2 — Map sticker**
1. Search for a town, city, or address.
2. Pick the map area (≈500 m / 1 km / 2 km, or a custom radius).
3. Toggle which feature categories to include (water, roads, green spaces, buildings,
   landmarks, recreation, food & drink), choose a label style (numbered legend or
   none), border, colors, and title/subtitle.
4. Two files are written to `output/`:
   - `<place>_map_editable.svg` — layered and editable
   - `<place>_map_cut.svg` — cut outline

### New Hampshire township map — `nh-map`

Non-interactive. Generates the base-map poster and all township stickers in one run:

```bash
# Generate the poster + one sticker per township into output/nh/
nh-map --out-dir output/nh
```

| Flag | Default | Description |
|------|---------|-------------|
| `--out-dir DIR` | `output` | Output directory |
| `--cache-dir DIR` | `.` | Base directory for the `.cache/` folder |
| `--year YYYY` | auto | Force a specific Census TIGER vintage (skips auto-resolve) |
| `--basemap-only` | off | Render only the poster, skip stickers |
| `--no-stickers` | off | Alias for `--basemap-only` |

By default the TIGER release year is resolved automatically to the latest published
vintage. Output layout:

```
output/nh/
  nh_basemap.svg                       # 24x36 in poster: state + county + township outlines, names
  stickers/
    <County>/
      <town>.svg                       # one die-cut sticker per township
```

Stickers cover **all NH county subdivisions** (~260), including unincorporated grants
and locations. Because the poster and every sticker share one projection scale, a
sticker's outline matches its slot on the poster exactly.

---

## Editing the SVGs

Open the **editable** files in Inkscape or Illustrator. Layers/groups are named so you
can target them directly:

- **Lake / map stickers:** shoreline / feature layers, `label`, and `border` groups.
- **Township stickers:** `cut` (the die-cut outline, with a small white kiss-cut
  border), `boundary` (the true town outline), `label` (the town name), and an
  **empty `artwork` group** centered on the shape — drop your unique per-town
  illustration into that group.

The **cut** files contain just the outline path for a vinyl cutter — no text or fill.

---

## Data sources & attribution

- **Lake & map stickers:** © OpenStreetMap contributors
  ([ODbL](https://www.openstreetmap.org/copyright)), via the Overpass API (and
  Nominatim for search; osmnx as an optional fallback).
- **NH township map:** US Census Bureau TIGER/Line shapefiles (public domain). County
  and state outlines are derived by dissolving township polygons.

Fetched data is cached under `.cache/` so re-runs don't re-download.

---

## Development

```bash
pip install -e ".[dev,townships]"
pytest
```

Tests are offline: network and geopandas/pyproj code paths are mocked or guarded with
`pytest.importorskip`, so the suite runs without the optional extras installed (those
specific tests skip).

## Project layout

```
lake_sticker/
  cli.py            # lake-sticker entry point (interactive)
  search.py         # OSM place/lake search (Nominatim)
  geometry.py       # geometry fetch + simplification + projection
  svg.py, borders.py, icons/   # lake sticker rendering
  map/              # map sticker mode (Overpass fetch, features, render, icons)
  townships/        # nh-map: TIGER data, projection, basemap + sticker renderers, CLI
docs/superpowers/   # design specs and implementation plans
tests/
```
