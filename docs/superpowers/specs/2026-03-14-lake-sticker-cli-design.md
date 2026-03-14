# Lake Sticker CLI — Design Spec

## Overview

An interactive command-line tool that fetches public map data for any lake, traces its outline, and outputs high-quality SVG files for vinyl sticker cutting on a Cricut. The output is a cute artistic interpretation — recognizable but not hyper-accurate — intended for further editing before final print.

## Package Structure

```
sticker-maker/
├── lake_sticker/
│   ├── __init__.py          # version, public API
│   ├── search.py            # lake search via Nominatim, disambiguation
│   ├── geometry.py          # fetch polygon, simplify, extract islands
│   ├── borders.py           # decorative border generators (dotted, double-line, dashed)
│   ├── svg.py               # SVG assembly (editable + cut-ready variants)
│   └── cli.py               # interactive CLI loop
├── output/                  # generated SVGs
├── generate_lake_svg.py     # original script, kept for reference
├── pyproject.toml           # dependencies + entry point
└── run.py                   # simple entry point: python run.py
```

## Dependencies

**Required:**
- `shapely` — geometry processing (simplify, unions, coordinate extraction)
- `requests` — HTTP calls to Nominatim/Overpass APIs

**Optional:**
- `osmnx` + `geopandas` — install with `pip install lake-sticker[osmnx]` for fallback geometry fetching. Not required — the primary pipeline uses Overpass + Nominatim directly, which avoids the heavy (~200MB) osmnx dependency tree.

## Interactive CLI Flow

```
$ python run.py

Lake Sticker Maker
=====================

Enter lake name: Crystal Lake

Searching OpenStreetMap...
Found 8 results:

  1) Crystal Lake — Gilmanton, Belknap County, NH
  2) Crystal Lake — Eaton, Carroll County, NH
  3) Crystal Lake — Enfield, Grafton County, NH
  ...

Select a lake [1-8]: 2

Fetching geometry for Crystal Lake (Eaton, NH)...
  Shoreline: 342 points (simplified)
  Islands: 2

Label: CRYSTAL LAKE
Subtitle: NEW HAMPSHIRE
Edit label? [y/N]: y
  Label [CRYSTAL LAKE]: _
  Subtitle [NEW HAMPSHIRE]: EATON, NH

Border style:
  1) Dotted ring
  2) Double-line frame
  3) Dashed ring
  4) None
Select border [1-4]: 1

Simplification (higher = smoother for vinyl):
  Current: 0.0003 (~33m)
  [Enter to keep, or type new value]: _

Colors:
  Fill [#1a3a5c]: _
  Label [#1a3a5c]: _

Generating SVGs...
  > output/crystal_lake_eaton_nh_editable.svg  (separate layers)
  > output/crystal_lake_eaton_nh_cut.svg       (single path, vinyl-ready)

Done! Open the editable SVG in Inkscape/Illustrator for final touches.
Generate another? [y/N]:
```

### Key behaviors

- Sensible defaults throughout — Enter skips through most prompts for quick generation.
- Single result auto-confirms: "Found Crystal Lake (Eaton, NH). Use this? [Y/n]"
- No results: suggests different spelling or adding a state.
- Too many results (>15): caps display at 15 with a note to narrow the search (e.g., "Crystal Lake, NH").
- File naming is automatic based on lake name + location, sanitized for filesystem (ASCII transliteration, non-alphanumeric replaced with underscores, lowercased). Handles non-ASCII names like "Lac-Saint-Jean" gracefully.
- No overwrites — appends `_2`, `_3`, etc. if file exists.
- `output/` directory is created automatically if missing.
- Loop at end to batch-generate multiple lakes in one session.

## Module Design

### search.py — Lake Search & Selection

**Responsibilities:** Query Nominatim for lakes by name, parse results into structured candidates, present disambiguation list.

**How it works:**
1. Query Nominatim with the user's input via free-text search. Do an unfiltered name search, then post-filter results client-side by checking for water-related OSM tags (`natural=water`, `water=lake`, `water=reservoir`, etc.) since OSM tagging is inconsistent across regions.
2. Parse display names to extract lake name, town/city, county, state/country. For multi-state lakes (e.g., Lake Champlain spanning VT/NY/QC), use the primary state from the Nominatim result; the user can edit the subtitle.
3. Return a list of candidate dicts: `{name, location_display, osm_id, osm_type, bbox}`.

**Why Nominatim for search:** Purpose-built for name search, returns structured location context. Overpass is better for geometry fetching (used in the next step).

**Rate limiting:** Proper User-Agent header (`lake-sticker-maker/1.0`), 1 request/second max per Nominatim policy.

### geometry.py — Polygon Fetch & Processing

**Responsibilities:** Fetch full polygon for a selected lake, merge multi-parts, simplify, extract islands.

**Pipeline:**
1. **Fetch** — Primary: query Overpass API using OSM ID for the full polygon (most reliable when we have a specific ID from Nominatim). Fallback 1: `osmnx.features_from_place()` if osmnx is installed. Fallback 2: Nominatim polygon output as last resort. Overpass is primary because we have the exact OSM ID, making it a targeted fetch rather than a search.
2. **Merge** — `unary_union` to combine MultiPolygon parts into one shape. All parts of a named lake (bays, separate basins) are unioned together rather than using only the largest part.
3. **Simplify** — `shapely.simplify()` with `preserve_topology=True`. Default tolerance auto-scales based on lake bounding box size (roughly 0.1% of the bbox diagonal), displayed to the user in degrees with an approximate meter conversion at the lake's latitude. User can override.
4. **Extract islands** — Pull interior rings, filter out islands below 0.01% of lake area.
5. **Project** — Transform lat/lon to SVG pixel coordinates, flip Y axis, scale to canvas, center with padding.

**Parameterized inputs:** OSM ID (from search), simplification tolerance (from user or auto-calculated), island area threshold (default with override).

**Caching:** Fetched geometries are cached locally in `.cache/` by OSM ID. Re-generating a previously fetched lake skips the API call. This avoids hitting Overpass rate limits during batch sessions.

### borders.py — Decorative Border Generators

**Responsibilities:** Generate SVG elements for each border style.

**Border styles:**
1. **Dotted ring** — Ellipse of evenly-spaced circles around lake bounding box + margin. Dot count auto-calculated from perimeter.
2. **Double-line frame** — Two concentric ellipses. Inner thinner, outer slightly thicker.
3. **Dashed ring** — Single ellipse with `stroke-dasharray`.

**Why ellipse (not lake-contour offset):** Polygon offsets produce self-intersection artifacts on concave shapes. Ellipses look intentionally designed, match the sticker aesthetic, and are simple for Cricut to cut.

**Output format:**
- For editable SVG: returns SVG group element (`<g id="border">...`).
- For cut-ready SVG: borders are generated as two concentric filled paths (inner and outer ellipse outlines) rather than stroked paths. This avoids the complexity of stroke-to-path conversion and ensures Cricut sees clean cut lines. For dotted borders, each dot is a small filled circle path.

### svg.py — SVG Assembly

**Responsibilities:** Compose final SVG files from geometry, border, and label components.

**Two output files:**

#### Editable SVG (`*_editable.svg`)
```xml
<svg>
  <g id="border">...</g>
  <g id="lake">
    <path id="lake-body" fill-rule="evenodd" .../>
    <!-- lake body + island cutouts in one path for correct rendering -->
  </g>
  <g id="label">
    <text id="title">CRYSTAL LAKE</text>
    <text id="subtitle">EATON, NH</text>
  </g>
</svg>
```
- Named groups for independent selection/editing.
- Lake uses `fill-rule="evenodd"` with islands as sub-paths (not white fills), so it renders correctly on any background color.
- Colors as fills. OSM attribution comment included.
- Border color is derived from the fill color (same color by default).

#### Cut-ready SVG (`*_cut.svg`)
- Lake + islands as single path with `fill-rule="evenodd"`.
- Border as path outlines (no strokes — Cricut cuts paths).
- No text (handled in editor or Cricut Design Space).
- Minimal SVG — just clean cut paths.

**Sizing:** 800px wide default, height auto from aspect ratio. `viewBox`-based for lossless scaling. Padding for border and breathing room.

### cli.py — Interactive CLI

**Responsibilities:** Orchestrate the full interactive flow: search, select, configure, generate, loop.

**Drives the flow described in the CLI section above.** Each step calls into the appropriate module. All user prompts have defaults so Enter skips through for quick generation.

## Error Handling

- **Network errors:** If Nominatim/Overpass is unreachable, display a clear message and suggest checking internet connection. No silent failures.
- **Rate limiting (429):** Wait and retry once with a brief pause. If still blocked, suggest trying again in a minute.
- **Unexpected geometry types:** If the fetched geometry is a LineString or Point instead of a Polygon, skip it and try the next fallback method. If all methods return non-polygon data, report "Could not get a polygon for this lake."
- **Geometry fetch failure:** Cascading fallback (Overpass → osmnx → Nominatim). If all three fail, report the error and let the user try a different lake rather than crashing.
- **Invalid user input:** Re-prompt on bad input (out-of-range selection, non-numeric values) rather than crashing.

## Entry Points

- `python run.py` — simple script entry point, no install required. Contains `from lake_sticker.cli import main; main()`.
- `lake-sticker` — console script entry point after `pip install -e .` (defined in pyproject.toml).
