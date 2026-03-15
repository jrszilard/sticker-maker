# Whimsical Map Sticker — Design Spec

## Overview

An extension to the lake sticker CLI that generates illustrated tourist-style map stickers from OpenStreetMap data. The maps use a warm, charming illustration style — simplified roads with hand-drawn curves, small recognizable landmark icons, decorative water features — designed to look like a cute souvenir sticker rather than an accurate map. Output is SVG for editing and Cricut vinyl cutting.

## Integration with Existing Tool

The CLI gets a mode selector at the top:

```
What would you like to create?
  1) Lake sticker
  2) Map sticker
Select [1-2]:
```

Option 1 runs the existing lake sticker flow unchanged. Option 2 enters the map sticker flow described below.

**Reused modules:**
- `search.py` — filename sanitization via `sanitize_filename()`. A new `search_location()` function is added (unlike `search_lakes()`, it does NOT filter by water features — it accepts towns, cities, neighborhoods, addresses). It also captures `lat`/`lon` from Nominatim results for center-point-based Overpass queries.
- `geometry.py` — `compute_projection()` and `coords_to_svg_path()` for coordinate transformation. Also `process_geometry()` for any lakes/ponds within the map area. Note: the map's Overpass querying is entirely new (`map/fetch.py`) since it's area-based, not single-element-based.
- `borders.py` — decorative sticker borders. New rectangular border variants are added for map stickers since maps are rectangular, not elliptical. Each existing ellipse function gets a rectangular counterpart with the same style: `dotted_rect(x, y, w, h, color, ...)`, `double_line_rect(x, y, w, h, color, ...)`, `dashed_rect(x, y, w, h, color, ...)`. These use rounded corners (`rx`/`ry` on SVG `<rect>`) for a softer look. The `BORDER_STYLES` dict gains a `RECT_BORDER_STYLES` companion. Existing ellipse-based borders remain for lake stickers.
- `cli.py` — modified to add the mode selector, shared input helpers

## Package Structure

```
lake_sticker/
├── __init__.py              # existing
├── search.py                # existing — reused for location search
├── geometry.py              # existing — reused for water features
├── borders.py               # existing — reused for sticker borders
├── svg.py                   # existing — lake SVG output
├── cli.py                   # modified — adds mode selector at top
├── map/
│   ├── __init__.py
│   ├── fetch.py             # fetch roads, POIs, water, green spaces from Overpass
│   ├── features.py          # classify and simplify map features
│   ├── layout.py            # position icons, compute label placement
│   ├── render.py            # compose the final SVG layers
│   ├── icons.py             # icon library loader + OSM tag mapping
│   └── cli.py               # map-specific interactive prompts
├── icons/                   # built-in SVG icon library
│   ├── mapping.json         # OSM tag → icon filename mapping
│   ├── church.svg
│   ├── restaurant.svg
│   ├── shop.svg
│   ├── house.svg
│   ├── tree.svg
│   ├── boat.svg
│   └── ...                  # ~25 icons total
└── user_icons/              # user-extensible icon folder (.gitignored)
    └── mapping.json         # user overrides for tag → icon mapping
```

## Dependencies

**New (in addition to existing):**
- None — the map feature uses the same stack (Shapely, requests) plus pure Python for Chaikin smoothing and SVG composition.

## Interactive CLI Flow

```
$ python run.py

Lake Sticker Maker
======================

What would you like to create?
  1) Lake sticker
  2) Map sticker
Select [1-2]: 2

Enter location (town, city, or address): Wolfeboro, NH

Searching OpenStreetMap...
  Found: Wolfeboro, Carroll County, New Hampshire

Map area:
  1) Small (few blocks, ~500m radius)
  2) Medium (neighborhood, ~1km radius)
  3) Large (town center, ~2km radius)
  4) Custom radius
Select [1-4]: 3

Fetching map data for Wolfeboro, NH (2km radius)...
  Roads: 47
  Water features: 3
  Buildings: 124
  Points of interest: 18

Feature categories to include:
  [x] Water (lakes, rivers)
  [x] Roads (main streets, paths)
  [x] Green spaces (parks, forests)
  [ ] Buildings (houses, shops)
  [x] Landmarks (churches, museums)
  [x] Recreation (marinas, beaches)
  [ ] Food & drink (restaurants, cafes)
Toggle categories? [y/N]: y
  Toggle which? (comma-separated numbers, e.g. 4,7): 4,7

Label style:
  1) Major features only (roads + water)
  2) Labels + numbered legend
  3) Selective labeling (configurable density)
  4) No labels
Select [1-4]: 2

Border style:
  1) Dotted border
  2) Double-line frame
  3) Dashed border
  4) None
Select [1-4]: 2

Colors:
  Water [#7eb8cc]: _
  Roads [#c9b88a]: _
  Green [#5a8f4a]: _
  Buildings [#d4816b]: _
  Labels [#3d405b]: _

Title: WOLFEBORO
Subtitle: NEW HAMPSHIRE
Edit title? [y/N]: _

Generating map sticker...
  > output/wolfeboro_nh_map_editable.svg  (layered, editable)
  > output/wolfeboro_nh_map_cut.svg       (cut outline)

Done! Open the editable SVG in Inkscape/Illustrator for final touches.
Generate another? [y/N]:
```

### Key behaviors

- Location search reuses existing Nominatim search from `search.py`.
- Area size is a radius around the center point. Overpass queries for everything inside that circle.
- Feature categories are shown with checkmarks based on what data was actually found. User toggles categories before rendering.
- Colors have sensible defaults for the "illustrated & charming" palette, all customizable.
- Same border options, file naming, no-overwrite, and loop behavior as lake stickers.
- Single result auto-confirms. No results suggests different spelling. Same UX patterns.

## Module Design

### map/fetch.py — Data Fetching

**Responsibilities:** Query Overpass for all map features within a radius of a center point. Return structured feature lists.

**Overpass query fetches:**
- **Roads:** `highway=*` — primary, secondary, tertiary, residential, pedestrian, footway
- **Water:** `natural=water`, `waterway=river/stream`, `water=*`
- **Green spaces:** `leisure=park/garden`, `landuse=forest/meadow`, `natural=wood`
- **Buildings:** `building=*` (with sub-tags like `building=church`, `building=commercial`)
- **POIs:** `amenity=*`, `tourism=*`, `historic=*`, `shop=*`, `leisure=marina/beach`

All fetched in a single compound Overpass query using `(around:RADIUS,LAT,LON)` filter and `out geom` output mode. POI point coordinates are extracted from the geometry (first coordinate or centroid). Example query skeleton:

```
[out:json][timeout:120];
(
  way["highway"](around:RADIUS,LAT,LON);
  way["natural"="water"](around:RADIUS,LAT,LON);
  relation["natural"="water"](around:RADIUS,LAT,LON);
  way["leisure"~"park|garden"](around:RADIUS,LAT,LON);
  way["landuse"~"forest|meadow"](around:RADIUS,LAT,LON);
  way["building"](around:RADIUS,LAT,LON);
  node["amenity"](around:RADIUS,LAT,LON);
  node["tourism"](around:RADIUS,LAT,LON);
  node["shop"](around:RADIUS,LAT,LON);
);
out geom;
```

**Output data structure:**

```python
{
    "type": "road" | "water" | "green" | "building" | "poi",
    "subtype": "primary_road" | "church" | "restaurant" | ...,
    "name": "Main Street" | None,
    "geometry": Shapely LineString/Polygon/Point,
    "osm_tags": {"highway": "primary", ...},
}
```

**Caching:** Cache raw Overpass response by center point (rounded to 4 decimal places) + radius in `.cache/`. Same caching infrastructure as `geometry.py`.

### map/features.py — Feature Processing & Simplification

**Responsibilities:** Filter, classify, and simplify raw map features into sticker-ready shapes.

**Roads:**
1. Filter by highway classification — keep primary, secondary, tertiary, residential. Drop service roads, driveways, construction.
2. Simplify geometry with Shapely `simplify(preserve_topology=True)`.
3. Smooth lines with Chaikin's corner-cutting algorithm (2 iterations, which is the standard for natural-looking curves without excessive point count). Each iteration roughly doubles the point count, so 2 iterations keeps SVG size manageable.
4. Classify by importance: main roads drawn thicker/darker, side streets thinner/lighter.

**Water:**
1. Lakes/ponds — reuse `geometry.process_geometry()` from existing module.
2. Rivers/streams — simplify LineString, apply Chaikin smoothing.
3. Generate decorative wave line paths inside water polygons (SVG squiggles placed along the surface).

**Green spaces:**
1. Simplify polygon boundaries.
2. Compute tree icon scatter positions inside polygons — randomized but with minimum spacing to avoid overlap. Density scales with polygon size.

**Buildings:**
1. Generic buildings — simplify to bounding rectangles. Only show buildings above a minimum size threshold.
2. Typed buildings (churches, museums, etc.) — promote to POI and assign an icon instead of drawing a footprint.

**POIs:**
1. Map OSM tags to icon categories using the icon mapping config.
2. Position at point coordinates or polygon centroid.
3. Scale icons by feature importance — major landmarks get slightly larger icons.

### map/layout.py — Layout & Label Placement

**Responsibilities:** Position icons to avoid overlaps, compute label positions, build numbered legend if selected.

**Icon collision avoidance:** Simple grid-based approach. Divide the canvas into cells, assign each icon to its cell. If two icons collide, nudge the less-important one to the nearest empty cell.

**Label placement strategies:**

1. **Major features only** — place road names along road paths using SVG `textPath`. Label water bodies at their centroid. Label the title.
2. **Labels + numbered legend** — place small numbered circles at POI positions. Build a legend box along one edge with numbered entries and names.
3. **Selective labeling** — label roads + top N most prominent POIs directly on the map. N is configurable (default: 10).
4. **No labels** — skip all text except the title.

**Road label placement:** Use SVG `<textPath>` to flow text along the road's smoothed path. Only label roads long enough to fit their name. Skip labels that would overlap.

### map/render.py — SVG Composition

**Responsibilities:** Compose the final SVG from processed features, icons, labels, border, and title.

**Layer order (bottom to top):**
1. Background — solid warm off-white (`#faf6f0`)
2. Green spaces — simplified polygons with green fill
3. Water — polygons with blue fill + decorative wave lines
4. Roads — two-stroke technique (wider light stroke, narrower darker stroke on top)
5. Building footprints — simplified rectangles for generic buildings
6. Icons — placed at POI coordinates via `<use>` references to `<defs>`
7. Labels — road names along paths, feature names, numbered markers
8. Title/subtitle — map title
9. Border — reuses `borders.py` generators
10. Legend — numbered legend if that label style was chosen

**Editable SVG (`*_map_editable.svg`):**

```xml
<svg>
  <defs>
    <!-- icon definitions -->
    <g id="icon-church">...</g>
    <g id="icon-restaurant">...</g>
  </defs>
  <g id="background">...</g>
  <g id="green-spaces">...</g>
  <g id="water">...</g>
  <g id="roads">...</g>
  <g id="buildings">...</g>
  <g id="icons">
    <use href="#icon-church" x="..." y="..." />
    <use href="#icon-restaurant" x="..." y="..." />
  </g>
  <g id="labels">...</g>
  <g id="title">...</g>
  <g id="border">...</g>
  <g id="legend">...</g>
</svg>
```

- Every layer is a named `<g>` group — toggle visibility, recolor, or rearrange in a vector editor.
- Icons use `<defs>` + `<use>` so each icon SVG is defined once and instanced multiple times.
- All text is editable `<text>` elements.
- OSM attribution comment included.

**Cut-ready SVG (`*_map_cut.svg`):**
- Contains only the outer sticker border shape — the Cricut cuts around the printed sticker.
- No map content inside. The workflow is: print the editable SVG on vinyl, use the cut SVG to tell the Cricut the cut outline.

**Sizing:** 800px wide default, viewBox-based, height auto from the map area's aspect ratio.

### map/icons.py — Icon Library & Mapping

**Responsibilities:** Load SVG icons from the icon library, resolve OSM tags to icon filenames.

**Built-in icon set (~25 icons):**

| Category | Icons |
|----------|-------|
| Worship | church, chapel |
| Food & Drink | restaurant, cafe, bar, brewery |
| Shopping | shop, market |
| Accommodation | hotel, inn |
| Culture | museum, library, theater |
| Recreation | marina, beach, playground, ski_area |
| Nature | tree, pine_tree, flower_garden |
| Infrastructure | lighthouse, bridge, parking |
| Residential | house, cabin |
| Water | boat, sailboat, kayak |

**mapping.json structure:**

```json
{
  "amenity=place_of_worship": "church",
  "amenity=restaurant": "restaurant",
  "amenity=cafe": "cafe",
  "tourism=museum": "museum",
  "tourism=hotel": "hotel",
  "leisure=marina": "marina",
  "shop=*": "shop",
  "building=church": "church"
}
```

- Uses `key=value` pairs from OSM tags.
- Wildcard `*` matches any value for that key.
- More specific matches take priority over wildcards.

**User-extensible:**
- Drop custom SVG into `user_icons/` (e.g., `user_icons/brewery.svg`).
- Add entry to `user_icons/mapping.json`: `{"craft=brewery": "brewery"}`.
- User mappings take priority over built-in ones.

**Icon SVG format:**
- Standalone SVG with `viewBox="0 0 40 40"` (consistent sizing).
- Illustrated & charming style: warm fills, thin outlines, small details (doors, crosses, windows).
- Colors use CSS custom properties (`var(--icon-primary, #d4816b)`) so the user's color palette applies at render time.

### map/cli.py — Map-Specific Prompts

**Responsibilities:** Handle the map-specific interactive prompts (area size, feature category toggles, label style, color palette).

Called from the main `cli.py` after the mode selector. Returns a config dict that `render.py` consumes:

```python
{
    "center": (43.58, -71.21),       # lat, lon from search
    "radius": 2000,                   # meters
    "categories": {
        "water": True, "roads": True, "green": True,
        "buildings": False, "landmarks": True,
        "recreation": True, "food_drink": False,
    },
    "label_style": "legend",          # "major", "legend", "selective", "none"
    "label_density": 10,              # only used if label_style == "selective"
    "border_style": "double_line",    # or "dotted", "dashed", None
    "colors": {
        "water": "#7eb8cc", "roads": "#c9b88a", "green": "#5a8f4a",
        "buildings": "#d4816b", "labels": "#3d405b",
    },
    "title": "WOLFEBORO",
    "subtitle": "NEW HAMPSHIRE",
}
```

## Icon Creation Strategy

The ~25 built-in icons are a design deliverable separate from the code implementation. The approach:

1. **v1 minimum viable set (8 icons):** tree, house, church, restaurant, shop, hotel, boat, pin (generic fallback). These cover the most common OSM POI categories and are sufficient for the tool to be usable. Implementation can proceed with simple geometric placeholder icons that match the charming style (colored shapes with minimal detail).

2. **Expanded set (post-v1):** Add the remaining ~17 icons incrementally. Each is a standalone SVG file dropped into `icons/` with a mapping entry — no code changes needed.

3. **Icon design specs:** Each icon is 40x40 viewBox, uses warm fills with thin outlines, includes one or two recognizable details (a cross on a church, a mast on a boat). Colors reference CSS custom properties with fallback defaults.

## Error Handling

- **Sparse data:** If the Overpass query returns very few features for the chosen area (e.g., rural area with 2 roads), warn the user and suggest increasing the radius.
- **No POIs:** If no points of interest are found, skip the icon layer and note it. The map still generates with roads/water/green.
- **Missing icon:** If a POI's OSM tags don't match any icon in the library, use a generic "pin" marker icon as fallback.
- **Label overlap:** When labels collide, drop the less-important one rather than rendering overlapping text.
- **Network errors:** Same handling as existing modules — clear messages, retry on 429.

## Visual Style Constants

Default "illustrated & charming" palette:

```python
COLORS = {
    "background": "#faf6f0",
    "water": "#7eb8cc",
    "water_waves": "#9dd0e0",
    "green": "#5a8f4a",
    "road_fill": "#c9b88a",
    "road_outline": "#d4c5a0",
    "building": "#d4816b",
    "label": "#3d405b",
    "title": "#3d405b",
}
```

Road widths by classification:
- Primary: 7px stroke
- Secondary/tertiary: 5px stroke
- Residential: 3px stroke
- Footway/path: 1.5px dashed stroke

Label font: `Georgia, 'Times New Roman', serif` (matching lake sticker labels).
