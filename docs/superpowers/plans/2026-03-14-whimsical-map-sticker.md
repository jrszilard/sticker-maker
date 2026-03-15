# Whimsical Map Sticker Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add illustrated tourist-style map sticker generation to the existing lake sticker CLI, using OpenStreetMap data with a warm, charming illustration style.

**Architecture:** New `lake_sticker/map/` subpackage with 6 modules (fetch, features, icons, layout, render, cli) plus modifications to 3 existing modules (search.py, borders.py, cli.py). Data flows: Overpass API → raw features → classified/simplified features → positioned layout → SVG composition. Built-in icon library (8 v1 icons) with user-extensible overrides.

**Tech Stack:** Python 3.12, Shapely (geometry), requests (HTTP), pytest (testing). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-03-14-whimsical-map-sticker-design.md`

---

## File Structure

```
lake_sticker/
├── search.py                # MODIFY: add search_location() + lat/lon capture
├── borders.py               # MODIFY: add dotted_rect, double_line_rect, dashed_rect + RECT_BORDER_STYLES
├── cli.py                   # MODIFY: add mode selector at top of main()
├── map/
│   ├── __init__.py          # CREATE: empty
│   ├── fetch.py             # CREATE: area-based Overpass query, caching, feature parsing
│   ├── features.py          # CREATE: Chaikin smoothing, road classification, building simplification
│   ├── icons.py             # CREATE: icon loader, OSM tag → icon mapping resolver
│   ├── layout.py            # CREATE: icon collision avoidance, label placement strategies
│   ├── render.py            # CREATE: SVG composition (10 layers), editable + cut-ready output
│   └── cli.py               # CREATE: map-specific interactive prompts, config dict builder
├── icons/
│   ├── mapping.json         # CREATE: OSM tag → icon filename mappings
│   ├── pin.svg              # CREATE: generic fallback marker
│   ├── tree.svg             # CREATE: nature tree icon
│   ├── house.svg            # CREATE: residential building
│   ├── church.svg           # CREATE: place of worship
│   ├── restaurant.svg       # CREATE: food/dining
│   ├── shop.svg             # CREATE: retail/shopping
│   ├── hotel.svg            # CREATE: accommodation
│   └── boat.svg             # CREATE: watercraft
tests/
├── test_search.py           # MODIFY: add tests for search_location
├── test_borders.py          # MODIFY: add tests for rectangular borders
├── test_map_fetch.py        # CREATE
├── test_map_features.py     # CREATE
├── test_map_icons.py        # CREATE
├── test_map_layout.py       # CREATE
├── test_map_render.py       # CREATE
```

---

## Chunk 1: Existing Module Modifications

### Task 1: Add `search_location()` to search.py

**Files:**
- Modify: `lake_sticker/search.py`
- Modify: `tests/test_search.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_search.py`:

```python
from lake_sticker.search import search_location, parse_location_results


def test_parse_location_results_accepts_towns():
    """parse_location_results should accept any place type, not just water."""
    raw = [
        {
            "place_id": 100,
            "osm_type": "relation",
            "osm_id": 55555,
            "display_name": "Wolfeboro, Carroll County, New Hampshire, USA",
            "class": "boundary",
            "type": "administrative",
            "lat": "43.5803",
            "lon": "-71.2076",
            "boundingbox": ["43.5", "43.7", "-71.3", "-71.1"],
        },
    ]
    results = parse_location_results(raw)
    assert len(results) == 1
    r = results[0]
    assert r["name"] == "Wolfeboro"
    assert r["lat"] == 43.5803
    assert r["lon"] == -71.2076
    assert r["osm_id"] == 55555


def test_parse_location_results_captures_lat_lon():
    """Each result must have numeric lat/lon for center-point queries."""
    raw = [
        {
            "place_id": 200,
            "osm_type": "way",
            "osm_id": 66666,
            "display_name": "King's Cross, London, England, UK",
            "class": "place",
            "type": "suburb",
            "lat": "51.5308",
            "lon": "-0.1238",
            "boundingbox": ["51.52", "51.54", "-0.14", "-0.11"],
        },
    ]
    results = parse_location_results(raw)
    assert isinstance(results[0]["lat"], float)
    assert isinstance(results[0]["lon"], float)


def test_parse_location_results_empty():
    """Empty response returns empty list."""
    assert parse_location_results([]) == []


def test_search_location_mocked(sample_nominatim_response):
    """search_location should query Nominatim without water filtering."""
    from unittest.mock import patch, Mock

    # Add lat/lon to the sample response items
    enriched = []
    for i, item in enumerate(sample_nominatim_response):
        item_copy = dict(item)
        item_copy["lat"] = str(43.5 + i * 0.1)
        item_copy["lon"] = str(-71.5 + i * 0.1)
        enriched.append(item_copy)

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = enriched
    mock_resp.raise_for_status = Mock()

    with patch("lake_sticker.search.requests.get", return_value=mock_resp):
        results = search_location("Wolfeboro, NH")

    # Should return ALL 3 results (no water filtering)
    assert len(results) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_search.py::test_parse_location_results_accepts_towns -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement `parse_location_results` and `search_location`**

Add to `lake_sticker/search.py`:

```python
def parse_location_results(raw_results):
    """Parse Nominatim results into location candidates (no water filtering).

    Unlike parse_nominatim_results(), this accepts any place type —
    towns, cities, neighborhoods, addresses — for map sticker use.

    Returns:
        List of dicts with keys: name, location_display, osm_id, osm_type,
        lat, lon, bbox.
    """
    candidates = []
    for r in raw_results:
        name, location_display = _parse_display_name(r.get("display_name", ""))
        try:
            lat = float(r["lat"])
            lon = float(r["lon"])
        except (KeyError, ValueError, TypeError):
            continue  # skip results without coordinates
        candidates.append({
            "name": name,
            "location_display": location_display,
            "osm_id": r["osm_id"],
            "osm_type": r["osm_type"],
            "lat": lat,
            "lon": lon,
            "bbox": r.get("boundingbox"),
        })
    return candidates


def search_location(query, max_results=15):
    """Search for any location (town, city, neighborhood, address).

    Unlike search_lakes(), this does NOT filter by water features.
    Results include lat/lon for center-point-based area queries.

    Args:
        query: location name (e.g. "Wolfeboro, NH").
        max_results: maximum results to return.

    Returns:
        List of candidate dicts (see parse_location_results).

    Raises:
        SearchError: on network errors or API failures.
    """
    _throttle_nominatim()

    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "json",
                "limit": 50,
                "addressdetails": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        if resp.status_code == 429:
            time.sleep(5)
            resp = requests.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 50, "addressdetails": 1},
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
        resp.raise_for_status()
    except requests.ConnectionError:
        raise SearchError("Could not connect to OpenStreetMap. Check your internet connection.")
    except requests.Timeout:
        raise SearchError("Search timed out. Try again in a moment.")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            raise SearchError("Rate limited by OpenStreetMap. Wait a minute and try again.")
        raise SearchError(f"Search failed: {e}")

    candidates = parse_location_results(resp.json())
    return candidates[:max_results]
```

- [ ] **Step 4: Run all search tests**

Run: `.venv/bin/pytest tests/test_search.py -v`
Expected: 12 passed (8 existing + 4 new)

- [ ] **Step 5: Commit**

```bash
git add lake_sticker/search.py tests/test_search.py
git commit -m "feat: add search_location() for general place search (no water filter)"
```

---

### Task 2: Add rectangular borders to borders.py

**Files:**
- Modify: `lake_sticker/borders.py`
- Modify: `tests/test_borders.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_borders.py`:

```python
from lake_sticker.borders import dotted_rect, double_line_rect, dashed_rect, RECT_BORDER_STYLES


def test_dotted_rect_returns_svg_group():
    svg = dotted_rect(x=50, y=50, w=700, h=500, color="#3d405b")
    assert '<g id="border">' in svg
    assert "<circle" in svg
    assert "</g>" in svg


def test_dotted_rect_dot_count():
    svg = dotted_rect(x=50, y=50, w=700, h=500, color="#3d405b")
    dot_count = svg.count("<circle")
    assert 20 <= dot_count <= 100


def test_double_line_rect_returns_svg_group():
    svg = double_line_rect(x=50, y=50, w=700, h=500, color="#3d405b")
    assert '<g id="border">' in svg
    assert "<rect" in svg
    assert "</g>" in svg


def test_double_line_rect_has_two_rects():
    svg = double_line_rect(x=50, y=50, w=700, h=500, color="#3d405b")
    assert svg.count("<rect") == 2


def test_dashed_rect_returns_svg_group():
    svg = dashed_rect(x=50, y=50, w=700, h=500, color="#3d405b")
    assert '<g id="border">' in svg
    assert "stroke-dasharray" in svg
    assert "</g>" in svg


def test_rect_border_styles_dict():
    assert "dotted" in RECT_BORDER_STYLES
    assert "double_line" in RECT_BORDER_STYLES
    assert "dashed" in RECT_BORDER_STYLES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_borders.py::test_dotted_rect_returns_svg_group -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement rectangular border functions**

Add to `lake_sticker/borders.py`:

```python
def dotted_rect(x, y, w, h, color, dot_radius=3, corner_radius=15, cut_ready=False):
    """Generate dots placed along a rounded rectangle border.

    Args:
        x, y: top-left corner of the rectangle
        w, h: width and height
        color: fill color for dots
        dot_radius: radius of each dot
        corner_radius: rounded corner radius
        cut_ready: unused (dots are always filled circles)
    """
    # Calculate perimeter of rounded rectangle
    straight = 2 * (w - 2 * corner_radius) + 2 * (h - 2 * corner_radius)
    corners = 2 * math.pi * corner_radius  # four quarter-circles = one full circle
    perimeter = straight + corners

    spacing = max(dot_radius * 10, 20)
    num_dots = max(12, int(perimeter / spacing))

    parts = ['  <g id="border">']

    for i in range(num_dots):
        t = i / num_dots
        px, py = _rect_point(x, y, w, h, corner_radius, t)
        parts.append(
            f'    <circle cx="{px:.1f}" cy="{py:.1f}" r="{dot_radius}" '
            f'fill="{color}" stroke="none"/>'
        )

    parts.append("  </g>")
    return "\n".join(parts)


def _rect_point(x, y, w, h, r, t):
    """Calculate a point at parameter t (0-1) along a rounded rectangle perimeter.

    Traverses: top edge, top-right corner, right edge, bottom-right corner,
    bottom edge, bottom-left corner, left edge, top-left corner.
    """
    # Straight segment lengths
    top = w - 2 * r
    right = h - 2 * r
    bottom = w - 2 * r
    left = h - 2 * r
    # Corner arc lengths (quarter circle each)
    corner_arc = math.pi * r / 2

    total = top + right + bottom + left + 4 * corner_arc
    d = t * total  # distance along perimeter

    # Top edge
    if d < top:
        return (x + r + d, y)
    d -= top

    # Top-right corner
    if d < corner_arc:
        angle = -math.pi / 2 + (d / corner_arc) * (math.pi / 2)
        return (x + w - r + r * math.cos(angle), y + r + r * math.sin(angle))
    d -= corner_arc

    # Right edge
    if d < right:
        return (x + w, y + r + d)
    d -= right

    # Bottom-right corner
    if d < corner_arc:
        angle = 0 + (d / corner_arc) * (math.pi / 2)
        return (x + w - r + r * math.cos(angle), y + h - r + r * math.sin(angle))
    d -= corner_arc

    # Bottom edge
    if d < bottom:
        return (x + w - r - d, y + h)
    d -= bottom

    # Bottom-left corner
    if d < corner_arc:
        angle = math.pi / 2 + (d / corner_arc) * (math.pi / 2)
        return (x + r + r * math.cos(angle), y + h - r + r * math.sin(angle))
    d -= corner_arc

    # Left edge
    if d < left:
        return (x, y + h - r - d)
    d -= left

    # Top-left corner
    angle = math.pi + (d / corner_arc) * (math.pi / 2)
    return (x + r + r * math.cos(angle), y + r + r * math.sin(angle))


def double_line_rect(x, y, w, h, color, gap=8, inner_width=1.5, outer_width=2.5,
                     corner_radius=15, cut_ready=False):
    """Generate two concentric rounded rectangles forming a double-line border."""
    parts = ['  <g id="border">']

    if cut_ready:
        # Outer rect
        parts.append(
            f'    <rect x="{x - outer_width / 2:.1f}" y="{y - outer_width / 2:.1f}" '
            f'width="{w + outer_width:.1f}" height="{h + outer_width:.1f}" '
            f'rx="{corner_radius}" fill="{color}" stroke="none"/>'
        )
        parts.append(
            f'    <rect x="{x + outer_width / 2:.1f}" y="{y + outer_width / 2:.1f}" '
            f'width="{w - outer_width:.1f}" height="{h - outer_width:.1f}" '
            f'rx="{corner_radius}" fill="white" stroke="none"/>'
        )
        # Inner rect
        inner_x, inner_y = x + gap, y + gap
        inner_w, inner_h = w - 2 * gap, h - 2 * gap
        parts.append(
            f'    <rect x="{inner_x - inner_width / 2:.1f}" y="{inner_y - inner_width / 2:.1f}" '
            f'width="{inner_w + inner_width:.1f}" height="{inner_h + inner_width:.1f}" '
            f'rx="{corner_radius}" fill="{color}" stroke="none"/>'
        )
        parts.append(
            f'    <rect x="{inner_x + inner_width / 2:.1f}" y="{inner_y + inner_width / 2:.1f}" '
            f'width="{inner_w - inner_width:.1f}" height="{inner_h - inner_width:.1f}" '
            f'rx="{corner_radius}" fill="white" stroke="none"/>'
        )
    else:
        parts.append(
            f'    <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{corner_radius}" fill="none" stroke="{color}" stroke-width="{outer_width}"/>'
        )
        inner_x, inner_y = x + gap, y + gap
        inner_w, inner_h = w - 2 * gap, h - 2 * gap
        parts.append(
            f'    <rect x="{inner_x:.1f}" y="{inner_y:.1f}" width="{inner_w:.1f}" height="{inner_h:.1f}" '
            f'rx="{corner_radius}" fill="none" stroke="{color}" stroke-width="{inner_width}"/>'
        )

    parts.append("  </g>")
    return "\n".join(parts)


def dashed_rect(x, y, w, h, color, dash_length=12, gap_length=8, stroke_width=2,
                corner_radius=15, cut_ready=False):
    """Generate a dashed rounded rectangle border."""
    parts = ['  <g id="border">']

    parts.append(
        f'    <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'rx="{corner_radius}" fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        f'stroke-dasharray="{dash_length} {gap_length}"/>'
    )

    parts.append("  </g>")
    return "\n".join(parts)


RECT_BORDER_STYLES = {
    "dotted": dotted_rect,
    "double_line": double_line_rect,
    "dashed": dashed_rect,
}
```

- [ ] **Step 4: Run all border tests**

Run: `.venv/bin/pytest tests/test_borders.py -v`
Expected: 14 passed (8 existing + 6 new)

- [ ] **Step 5: Commit**

```bash
git add lake_sticker/borders.py tests/test_borders.py
git commit -m "feat: add rectangular border variants for map stickers"
```

---

## Chunk 2: Map Data Pipeline (fetch + features)

### Task 3: Map data fetching (map/fetch.py)

**Files:**
- Create: `lake_sticker/map/__init__.py`
- Create: `lake_sticker/map/fetch.py`
- Create: `tests/test_map_fetch.py`

- [ ] **Step 1: Create `lake_sticker/map/__init__.py`**

Empty file.

- [ ] **Step 2: Write failing tests**

`tests/test_map_fetch.py`:

```python
"""Tests for lake_sticker.map.fetch module."""

from unittest.mock import patch, Mock
from lake_sticker.map.fetch import fetch_map_data, parse_overpass_elements, build_overpass_query


def test_build_overpass_query():
    """Query should use around filter with lat/lon/radius."""
    query = build_overpass_query(lat=43.58, lon=-71.21, radius=2000)
    assert "around:2000,43.58,-71.21" in query
    assert "highway" in query
    assert "natural" in query
    assert "building" in query
    assert "amenity" in query
    assert "out geom" in query


def test_parse_overpass_elements_roads():
    """Way elements with highway tag should become road features."""
    elements = [
        {
            "type": "way",
            "id": 1,
            "tags": {"highway": "primary", "name": "Main Street"},
            "geometry": [
                {"lat": 43.5, "lon": -71.5},
                {"lat": 43.51, "lon": -71.49},
                {"lat": 43.52, "lon": -71.48},
            ],
        },
    ]
    features = parse_overpass_elements(elements)
    assert len(features) == 1
    assert features[0]["type"] == "road"
    assert features[0]["name"] == "Main Street"
    assert features[0]["geometry"].geom_type == "LineString"


def test_parse_overpass_elements_pois():
    """Node elements with amenity/tourism tags should become POI features."""
    elements = [
        {
            "type": "node",
            "id": 2,
            "tags": {"amenity": "restaurant", "name": "Joe's Diner"},
            "lat": 43.55,
            "lon": -71.45,
        },
    ]
    features = parse_overpass_elements(elements)
    assert len(features) == 1
    assert features[0]["type"] == "poi"
    assert features[0]["name"] == "Joe's Diner"
    assert features[0]["geometry"].geom_type == "Point"


def test_parse_overpass_elements_water():
    """Way elements with natural=water should become water features."""
    elements = [
        {
            "type": "way",
            "id": 3,
            "tags": {"natural": "water", "name": "Crystal Lake"},
            "geometry": [
                {"lat": 43.5, "lon": -71.5},
                {"lat": 43.5, "lon": -71.4},
                {"lat": 43.6, "lon": -71.4},
                {"lat": 43.6, "lon": -71.5},
                {"lat": 43.5, "lon": -71.5},
            ],
        },
    ]
    features = parse_overpass_elements(elements)
    assert len(features) == 1
    assert features[0]["type"] == "water"


def test_parse_overpass_elements_buildings():
    """Way elements with building tag should become building features."""
    elements = [
        {
            "type": "way",
            "id": 4,
            "tags": {"building": "yes"},
            "geometry": [
                {"lat": 43.55, "lon": -71.45},
                {"lat": 43.55, "lon": -71.44},
                {"lat": 43.56, "lon": -71.44},
                {"lat": 43.56, "lon": -71.45},
                {"lat": 43.55, "lon": -71.45},
            ],
        },
    ]
    features = parse_overpass_elements(elements)
    assert len(features) == 1
    assert features[0]["type"] == "building"


def test_parse_overpass_elements_green():
    """Way elements with leisure=park should become green features."""
    elements = [
        {
            "type": "way",
            "id": 5,
            "tags": {"leisure": "park", "name": "Town Green"},
            "geometry": [
                {"lat": 43.55, "lon": -71.45},
                {"lat": 43.55, "lon": -71.44},
                {"lat": 43.56, "lon": -71.44},
                {"lat": 43.56, "lon": -71.45},
                {"lat": 43.55, "lon": -71.45},
            ],
        },
    ]
    features = parse_overpass_elements(elements)
    assert len(features) == 1
    assert features[0]["type"] == "green"


def test_fetch_map_data_mocked(tmp_path):
    """fetch_map_data should query Overpass and return parsed features."""
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "elements": [
            {
                "type": "way",
                "id": 1,
                "tags": {"highway": "residential", "name": "Oak St"},
                "geometry": [
                    {"lat": 43.5, "lon": -71.5},
                    {"lat": 43.51, "lon": -71.49},
                ],
            },
        ]
    }
    mock_resp.raise_for_status = Mock()

    with patch("lake_sticker.map.fetch.requests.get", return_value=mock_resp):
        features = fetch_map_data(lat=43.58, lon=-71.21, radius=2000, cache_dir=tmp_path)

    assert len(features) == 1
    assert features[0]["type"] == "road"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_map_fetch.py -v`
Expected: FAIL — ImportError

- [ ] **Step 4: Implement `map/fetch.py`**

`lake_sticker/map/fetch.py`:

```python
"""Fetch map data from the Overpass API for a geographic area."""

import json
import time
from pathlib import Path

import requests
from shapely.geometry import Point, LineString, Polygon

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CACHE_DIR = Path(".cache")

# Tag classification rules: (tag_key, tag_value_or_None) → feature_type
# Order matters — first match wins
_CLASSIFICATION_RULES = [
    ("highway", None, "road"),
    ("waterway", None, "water"),
    ("natural", "water", "water"),
    ("water", None, "water"),
    ("leisure", "park", "green"),
    ("leisure", "garden", "green"),
    ("landuse", "forest", "green"),
    ("landuse", "meadow", "green"),
    ("natural", "wood", "green"),
    ("building", None, "building"),
    ("amenity", None, "poi"),
    ("tourism", None, "poi"),
    ("historic", None, "poi"),
    ("shop", None, "poi"),
    ("leisure", "marina", "poi"),
    ("leisure", "beach_resort", "poi"),
]


def build_overpass_query(lat, lon, radius):
    """Build an Overpass QL query for all map features within a radius.

    Args:
        lat, lon: center point coordinates
        radius: search radius in meters

    Returns:
        Overpass QL query string
    """
    around = f"around:{radius},{lat},{lon}"
    return f"""[out:json][timeout:120];
(
  way["highway"]({around});
  way["natural"="water"]({around});
  relation["natural"="water"]({around});
  way["waterway"]({around});
  way["leisure"~"park|garden"]({around});
  way["landuse"~"forest|meadow"]({around});
  way["natural"="wood"]({around});
  way["building"]({around});
  node["amenity"]({around});
  node["tourism"]({around});
  node["historic"]({around});
  node["shop"]({around});
  node["leisure"~"marina|beach_resort"]({around});
);
out geom;"""


def _classify_element(tags):
    """Classify an OSM element by its tags into a feature type.

    Returns:
        Tuple of (type, subtype) or None if unclassifiable.
    """
    for tag_key, tag_val, feat_type in _CLASSIFICATION_RULES:
        if tag_key in tags:
            if tag_val is None or tags[tag_key] == tag_val:
                subtype = f"{tag_key}_{tags[tag_key]}" if tag_key in tags else feat_type
                return feat_type, subtype
    return None, None


def _build_geometry(element):
    """Build a Shapely geometry from an Overpass element."""
    if element["type"] == "node":
        return Point(element["lon"], element["lat"])

    if "geometry" not in element:
        return None

    coords = [(p["lon"], p["lat"]) for p in element["geometry"]]

    if len(coords) < 2:
        return None

    # Closed way = polygon, open way = linestring
    if len(coords) >= 4 and coords[0] == coords[-1]:
        try:
            return Polygon(coords)
        except Exception:
            return LineString(coords)

    return LineString(coords)


def parse_overpass_elements(elements):
    """Parse Overpass JSON elements into structured feature dicts.

    Args:
        elements: list of Overpass element dicts

    Returns:
        List of feature dicts with keys: type, subtype, name, geometry, osm_tags
    """
    features = []
    for el in elements:
        tags = el.get("tags", {})
        feat_type, subtype = _classify_element(tags)
        if feat_type is None:
            continue

        geom = _build_geometry(el)
        if geom is None:
            continue

        features.append({
            "type": feat_type,
            "subtype": subtype,
            "name": tags.get("name"),
            "geometry": geom,
            "osm_tags": tags,
        })

    return features


def fetch_map_data(lat, lon, radius, cache_dir=None):
    """Fetch all map features within a radius of a center point.

    Args:
        lat, lon: center coordinates
        radius: search radius in meters
        cache_dir: cache directory (default: .cache/)

    Returns:
        List of feature dicts (see parse_overpass_elements)
    """
    if cache_dir is None:
        cache_dir = CACHE_DIR
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Cache key from rounded coordinates + radius
    cache_key = f"map_{lat:.4f}_{lon:.4f}_{radius}"
    cache_file = cache_dir / f"{cache_key}.json"

    # Try cache
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            return parse_overpass_elements(data.get("elements", []))
        except (json.JSONDecodeError, Exception):
            pass

    # Query Overpass
    query = build_overpass_query(lat, lon, radius)
    try:
        resp = requests.get(OVERPASS_URL, params={"data": query}, timeout=120)
        if resp.status_code == 429:
            time.sleep(5)
            resp = requests.get(OVERPASS_URL, params={"data": query}, timeout=120)
        resp.raise_for_status()
    except requests.ConnectionError:
        raise RuntimeError("Could not connect to Overpass API. Check your internet connection.")
    except requests.Timeout:
        raise RuntimeError("Overpass query timed out. Try a smaller radius.")
    except requests.HTTPError as e:
        raise RuntimeError(f"Overpass query failed: {e}")

    data = resp.json()

    # Cache the response
    try:
        cache_file.write_text(json.dumps(data))
    except Exception:
        pass

    return parse_overpass_elements(data.get("elements", []))
```

- [ ] **Step 5: Run all fetch tests**

Run: `.venv/bin/pytest tests/test_map_fetch.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add lake_sticker/map/ tests/test_map_fetch.py
git commit -m "feat: map data fetching from Overpass with area query and caching"
```

---

### Task 4: Feature processing and Chaikin smoothing (map/features.py)

**Files:**
- Create: `lake_sticker/map/features.py`
- Create: `tests/test_map_features.py`

- [ ] **Step 1: Write failing tests**

`tests/test_map_features.py`:

```python
"""Tests for lake_sticker.map.features module."""

from shapely.geometry import LineString, Polygon, Point
from lake_sticker.map.features import (
    chaikin_smooth,
    classify_road,
    filter_roads,
    simplify_buildings,
    process_map_features,
)


def test_chaikin_smooth_produces_more_points():
    """Chaikin smoothing should increase point count."""
    coords = [(0, 0), (1, 0), (1, 1), (0, 1)]
    smoothed = chaikin_smooth(coords, iterations=2)
    assert len(smoothed) > len(coords)


def test_chaikin_smooth_preserves_approximate_shape():
    """Smoothed line should stay close to original."""
    coords = [(0, 0), (10, 0), (10, 10)]
    smoothed = chaikin_smooth(coords, iterations=2)
    # First point should be near origin, last near (10,10)
    assert abs(smoothed[0][0]) < 3
    assert abs(smoothed[-1][0] - 10) < 3


def test_classify_road_primary():
    """Primary highways should be classified as 'primary'."""
    assert classify_road({"highway": "primary"}) == "primary"
    assert classify_road({"highway": "primary_link"}) == "primary"


def test_classify_road_secondary():
    assert classify_road({"highway": "secondary"}) == "secondary"
    assert classify_road({"highway": "tertiary"}) == "secondary"


def test_classify_road_residential():
    assert classify_road({"highway": "residential"}) == "residential"


def test_classify_road_footway():
    assert classify_road({"highway": "footway"}) == "footway"
    assert classify_road({"highway": "path"}) == "footway"


def test_classify_road_excluded():
    """Service roads, driveways, construction should return None."""
    assert classify_road({"highway": "service"}) is None
    assert classify_road({"highway": "construction"}) is None


def test_filter_roads():
    """filter_roads should drop excluded road types."""
    features = [
        {"type": "road", "osm_tags": {"highway": "primary"}, "geometry": LineString([(0, 0), (1, 1)]), "name": "Main", "subtype": ""},
        {"type": "road", "osm_tags": {"highway": "service"}, "geometry": LineString([(0, 0), (1, 1)]), "name": None, "subtype": ""},
    ]
    filtered = filter_roads(features)
    assert len(filtered) == 1
    assert filtered[0]["name"] == "Main"


def test_simplify_buildings():
    """Buildings below threshold should be dropped."""
    small = Polygon([(0, 0), (0.00001, 0), (0.00001, 0.00001), (0, 0.00001), (0, 0)])
    big = Polygon([(0, 0), (0.001, 0), (0.001, 0.001), (0, 0.001), (0, 0)])
    features = [
        {"type": "building", "geometry": small, "name": None, "subtype": "", "osm_tags": {}},
        {"type": "building", "geometry": big, "name": None, "subtype": "", "osm_tags": {}},
    ]
    result = simplify_buildings(features, min_area=0.0000001)
    assert len(result) == 1  # small one dropped


def test_process_map_features_returns_categorized():
    """process_map_features should return a dict with categorized feature lists."""
    features = [
        {"type": "road", "subtype": "highway_primary", "name": "Main St",
         "geometry": LineString([(0, 0), (1, 0), (1, 1)]), "osm_tags": {"highway": "primary"}},
        {"type": "water", "subtype": "natural_water", "name": "Lake",
         "geometry": Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]), "osm_tags": {"natural": "water"}},
        {"type": "poi", "subtype": "amenity_restaurant", "name": "Joe's",
         "geometry": Point(0.5, 0.5), "osm_tags": {"amenity": "restaurant"}},
    ]
    result = process_map_features(features)
    assert "roads" in result
    assert "water" in result
    assert "pois" in result
    assert len(result["roads"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_map_features.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement `map/features.py`**

`lake_sticker/map/features.py`:

```python
"""Process and simplify map features for sticker rendering."""

from shapely.geometry import LineString, Polygon, Point
from shapely import simplify as shapely_simplify


# Road classification mapping
_ROAD_CLASSES = {
    "motorway": "primary",
    "motorway_link": "primary",
    "trunk": "primary",
    "trunk_link": "primary",
    "primary": "primary",
    "primary_link": "primary",
    "secondary": "secondary",
    "secondary_link": "secondary",
    "tertiary": "secondary",
    "tertiary_link": "secondary",
    "residential": "residential",
    "living_street": "residential",
    "unclassified": "residential",
    "pedestrian": "footway",
    "footway": "footway",
    "path": "footway",
    "cycleway": "footway",
    "track": "footway",
}

# Excluded road types
_EXCLUDED_ROADS = {"service", "construction", "proposed", "raceway", "bus_guideway"}


def chaikin_smooth(coords, iterations=2):
    """Smooth a coordinate list using Chaikin's corner-cutting algorithm.

    Each iteration replaces each segment with two new points at 1/4 and 3/4
    positions, producing a smoother curve. Two iterations is standard for
    natural-looking curves.

    Args:
        coords: list of (x, y) tuples
        iterations: number of smoothing passes (default 2)

    Returns:
        Smoothed list of (x, y) tuples
    """
    for _ in range(iterations):
        if len(coords) < 2:
            return coords
        new_coords = []
        for i in range(len(coords) - 1):
            x0, y0 = coords[i]
            x1, y1 = coords[i + 1]
            new_coords.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
            new_coords.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
        coords = new_coords
    return coords


def classify_road(tags):
    """Classify a road by its highway tag.

    Returns:
        'primary', 'secondary', 'residential', 'footway', or None (excluded)
    """
    highway = tags.get("highway", "")
    if highway in _EXCLUDED_ROADS:
        return None
    return _ROAD_CLASSES.get(highway)


def filter_roads(features):
    """Filter road features, dropping excluded types."""
    result = []
    for f in features:
        if f["type"] != "road":
            continue
        classification = classify_road(f["osm_tags"])
        if classification is not None:
            f["road_class"] = classification
            result.append(f)
    return result


def simplify_buildings(features, min_area=0.0000005):
    """Filter buildings by minimum area, dropping tiny structures."""
    result = []
    for f in features:
        if f["type"] != "building":
            continue
        if f["geometry"].geom_type == "Polygon" and f["geometry"].area >= min_area:
            result.append(f)
    return result


def _smooth_roads(roads, tolerance=0.00005):
    """Simplify and smooth road geometries."""
    for road in roads:
        geom = road["geometry"]
        if geom.geom_type == "LineString":
            simplified = shapely_simplify(geom, tolerance=tolerance, preserve_topology=True)
            coords = list(simplified.coords)
            smoothed = chaikin_smooth(coords, iterations=2)
            road["geometry"] = LineString(smoothed)
            road["smoothed_coords"] = smoothed
    return roads


def process_map_features(features):
    """Process raw features into categorized, simplified groups.

    Args:
        features: list of feature dicts from fetch.py

    Returns:
        Dict with keys: roads, water, green, buildings, pois
        Each value is a list of processed feature dicts.
    """
    roads = filter_roads([f for f in features if f["type"] == "road"])
    roads = _smooth_roads(roads)

    water = [f for f in features if f["type"] == "water"]
    green = [f for f in features if f["type"] == "green"]
    buildings = simplify_buildings([f for f in features if f["type"] == "building"])
    pois = [f for f in features if f["type"] == "poi"]

    # Promote typed buildings to POIs
    promoted = []
    remaining_buildings = []
    for b in buildings:
        tags = b["osm_tags"]
        building_type = tags.get("building", "yes")
        if building_type in ("church", "cathedral", "chapel", "mosque",
                             "museum", "hotel", "school", "hospital"):
            b["type"] = "poi"
            b["geometry"] = b["geometry"].centroid
            promoted.append(b)
        else:
            remaining_buildings.append(b)

    pois.extend(promoted)

    return {
        "roads": roads,
        "water": water,
        "green": green,
        "buildings": remaining_buildings,
        "pois": pois,
    }
```

- [ ] **Step 4: Run all feature tests**

Run: `.venv/bin/pytest tests/test_map_features.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add lake_sticker/map/features.py tests/test_map_features.py
git commit -m "feat: map feature processing with Chaikin smoothing and road classification"
```

---

## Chunk 3: Icon System + Layout

### Task 5: Icon library and mapping (map/icons.py)

**Files:**
- Create: `lake_sticker/map/icons.py`
- Create: `lake_sticker/icons/mapping.json`
- Create: `lake_sticker/icons/pin.svg` (+ 7 more v1 icons)
- Create: `tests/test_map_icons.py`

- [ ] **Step 1: Write failing tests**

`tests/test_map_icons.py`:

```python
"""Tests for lake_sticker.map.icons module."""

import json
from pathlib import Path
from lake_sticker.map.icons import load_icon_mapping, resolve_icon, load_icon_svg


def test_load_icon_mapping():
    """Should load the built-in mapping.json."""
    mapping = load_icon_mapping()
    assert "amenity=restaurant" in mapping
    assert mapping["amenity=restaurant"] == "restaurant"
    assert "amenity=place_of_worship" in mapping


def test_resolve_icon_exact_match():
    """Exact tag match should return the mapped icon name."""
    mapping = {"amenity=restaurant": "restaurant"}
    assert resolve_icon({"amenity": "restaurant"}, mapping) == "restaurant"


def test_resolve_icon_wildcard():
    """Wildcard match should work when no exact match."""
    mapping = {"shop=*": "shop"}
    assert resolve_icon({"shop": "bakery"}, mapping) == "shop"


def test_resolve_icon_specific_over_wildcard():
    """Specific match takes priority over wildcard."""
    mapping = {"shop=*": "shop", "shop=supermarket": "market"}
    assert resolve_icon({"shop": "supermarket"}, mapping) == "market"


def test_resolve_icon_fallback():
    """Unknown tags should return 'pin' fallback."""
    mapping = {"amenity=restaurant": "restaurant"}
    assert resolve_icon({"unknown_tag": "value"}, mapping) == "pin"


def test_load_icon_svg():
    """Should load an SVG file from the icons directory."""
    svg = load_icon_svg("pin")
    assert "<svg" in svg or "<g" in svg or "<circle" in svg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_map_icons.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Create `icons/mapping.json`**

`lake_sticker/icons/mapping.json`:

```json
{
  "amenity=place_of_worship": "church",
  "building=church": "church",
  "building=cathedral": "church",
  "building=chapel": "church",
  "amenity=restaurant": "restaurant",
  "amenity=fast_food": "restaurant",
  "amenity=cafe": "restaurant",
  "amenity=bar": "restaurant",
  "amenity=pub": "restaurant",
  "shop=*": "shop",
  "tourism=hotel": "hotel",
  "tourism=motel": "hotel",
  "tourism=guest_house": "hotel",
  "building=hotel": "hotel",
  "tourism=museum": "pin",
  "tourism=attraction": "pin",
  "historic=*": "pin",
  "leisure=marina": "boat",
  "building=*": "house",
  "natural=tree": "tree"
}
```

- [ ] **Step 4: Create v1 icon SVGs (8 icons)**

Create these files in `lake_sticker/icons/`. Each is a simple 40x40 SVG in the charming illustrated style:

`lake_sticker/icons/pin.svg` — generic marker (circle with dot):
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
  <circle cx="20" cy="16" r="10" fill="var(--icon-primary, #e07a5f)" stroke="var(--icon-outline, #5a3e36)" stroke-width="1.5"/>
  <circle cx="20" cy="16" r="3" fill="white"/>
  <path d="M20,26 L20,35" stroke="var(--icon-outline, #5a3e36)" stroke-width="2" stroke-linecap="round"/>
</svg>
```

`lake_sticker/icons/tree.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
  <ellipse cx="20" cy="15" rx="12" ry="14" fill="var(--icon-primary, #5a8f4a)" stroke="var(--icon-outline, #3d6b35)" stroke-width="1"/>
  <rect x="18" y="27" width="4" height="8" rx="1" fill="var(--icon-outline, #7a5c3a)"/>
</svg>
```

`lake_sticker/icons/house.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
  <rect x="8" y="20" width="24" height="16" rx="1" fill="var(--icon-primary, #e8c86e)" stroke="var(--icon-outline, #5a3e36)" stroke-width="1"/>
  <polygon points="20,8 4,20 36,20" fill="var(--icon-secondary, #c0392b)" stroke="var(--icon-outline, #5a3e36)" stroke-width="1"/>
  <rect x="16" y="26" width="8" height="10" rx="1" fill="var(--icon-outline, #8e6e53)"/>
</svg>
```

`lake_sticker/icons/church.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
  <rect x="10" y="18" width="20" height="18" rx="1" fill="var(--icon-primary, #d4816b)" stroke="var(--icon-outline, #5a3e36)" stroke-width="1"/>
  <polygon points="20,10 10,18 30,18" fill="var(--icon-primary, #d4816b)" stroke="var(--icon-outline, #5a3e36)" stroke-width="1"/>
  <line x1="20" y1="4" x2="20" y2="10" stroke="var(--icon-outline, #5a3e36)" stroke-width="1.5"/>
  <line x1="17" y1="7" x2="23" y2="7" stroke="var(--icon-outline, #5a3e36)" stroke-width="1.5"/>
</svg>
```

`lake_sticker/icons/restaurant.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
  <rect x="8" y="16" width="24" height="18" rx="2" fill="var(--icon-primary, #e07a5f)" stroke="var(--icon-outline, #5a3e36)" stroke-width="1"/>
  <rect x="12" y="12" width="16" height="6" rx="1" fill="var(--icon-secondary, #c9b88a)" stroke="var(--icon-outline, #5a3e36)" stroke-width="1"/>
  <rect x="14" y="22" width="5" height="5" rx="0.5" fill="white" opacity="0.6"/>
  <rect x="21" y="22" width="5" height="5" rx="0.5" fill="white" opacity="0.6"/>
</svg>
```

`lake_sticker/icons/shop.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
  <rect x="8" y="16" width="24" height="18" rx="1" fill="var(--icon-primary, #ffd93d)" stroke="var(--icon-outline, #5a3e36)" stroke-width="1"/>
  <rect x="6" y="12" width="28" height="6" rx="1" fill="var(--icon-secondary, #e07a5f)" stroke="var(--icon-outline, #5a3e36)" stroke-width="1"/>
  <rect x="12" y="20" width="16" height="8" rx="1" fill="white" opacity="0.5"/>
</svg>
```

`lake_sticker/icons/hotel.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
  <rect x="8" y="10" width="24" height="26" rx="1" fill="var(--icon-primary, #d4816b)" stroke="var(--icon-outline, #5a3e36)" stroke-width="1"/>
  <rect x="12" y="14" width="6" height="5" rx="0.5" fill="white" opacity="0.6"/>
  <rect x="22" y="14" width="6" height="5" rx="0.5" fill="white" opacity="0.6"/>
  <rect x="12" y="22" width="6" height="5" rx="0.5" fill="white" opacity="0.6"/>
  <rect x="22" y="22" width="6" height="5" rx="0.5" fill="white" opacity="0.6"/>
  <rect x="16" y="30" width="8" height="6" rx="1" fill="var(--icon-outline, #8e6e53)"/>
</svg>
```

`lake_sticker/icons/boat.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
  <path d="M8,28 Q12,22 20,22 Q28,22 32,28 Z" fill="var(--icon-primary, #c0392b)" stroke="var(--icon-outline, #5a3e36)" stroke-width="1"/>
  <line x1="20" y1="10" x2="20" y2="22" stroke="var(--icon-outline, #5a3e36)" stroke-width="1.5"/>
  <polygon points="20,10 30,18 20,18" fill="white" stroke="var(--icon-outline, #5a3e36)" stroke-width="0.5"/>
  <path d="M6,32 Q13,29 20,32 Q27,35 34,32" fill="none" stroke="var(--icon-primary, #7eb8cc)" stroke-width="1.5"/>
</svg>
```

- [ ] **Step 5: Implement `map/icons.py`**

`lake_sticker/map/icons.py`:

```python
"""Icon library loader and OSM tag → icon mapping."""

import json
from pathlib import Path

_ICONS_DIR = Path(__file__).parent.parent / "icons"
_USER_ICONS_DIR = Path("user_icons")


def load_icon_mapping(user_dir=None):
    """Load icon mapping from built-in and user directories.

    User mappings take priority over built-in ones.

    Returns:
        Dict mapping "key=value" strings to icon names.
    """
    mapping = {}

    # Load built-in mapping
    builtin_path = _ICONS_DIR / "mapping.json"
    if builtin_path.exists():
        mapping.update(json.loads(builtin_path.read_text()))

    # Load user overrides
    if user_dir is None:
        user_dir = _USER_ICONS_DIR
    user_path = Path(user_dir) / "mapping.json"
    if user_path.exists():
        mapping.update(json.loads(user_path.read_text()))

    return mapping


def resolve_icon(osm_tags, mapping):
    """Resolve OSM tags to an icon name using the mapping.

    Tries specific matches first, then wildcard matches.
    Falls back to 'pin' if nothing matches.

    Args:
        osm_tags: dict of OSM tags (e.g., {"amenity": "restaurant"})
        mapping: dict from load_icon_mapping()

    Returns:
        Icon name string (e.g., "restaurant")
    """
    # Try specific matches first
    for key, value in osm_tags.items():
        specific = f"{key}={value}"
        if specific in mapping:
            return mapping[specific]

    # Try wildcard matches
    for key in osm_tags:
        wildcard = f"{key}=*"
        if wildcard in mapping:
            return mapping[wildcard]

    return "pin"


def load_icon_svg(icon_name, user_dir=None):
    """Load an icon SVG file by name.

    Checks user_icons/ first, then built-in icons/.

    Args:
        icon_name: icon filename without .svg extension

    Returns:
        SVG file contents as string.

    Raises:
        FileNotFoundError: if icon not found in either directory.
    """
    if user_dir is None:
        user_dir = _USER_ICONS_DIR

    # Check user icons first
    user_path = Path(user_dir) / f"{icon_name}.svg"
    if user_path.exists():
        return user_path.read_text()

    # Check built-in icons
    builtin_path = _ICONS_DIR / f"{icon_name}.svg"
    if builtin_path.exists():
        return builtin_path.read_text()

    raise FileNotFoundError(f"Icon '{icon_name}' not found in {user_dir} or {_ICONS_DIR}")
```

- [ ] **Step 6: Run all icon tests**

Run: `.venv/bin/pytest tests/test_map_icons.py -v`
Expected: 6 passed

- [ ] **Step 7: Add `user_icons/` to .gitignore and create placeholder directory**

Append to `.gitignore`:
```
user_icons/
```

Create `user_icons/` directory with a placeholder `mapping.json`:
```json
{}
```

- [ ] **Step 8: Commit**

```bash
git add lake_sticker/map/icons.py lake_sticker/icons/ tests/test_map_icons.py .gitignore user_icons/mapping.json
git commit -m "feat: icon library with 8 v1 icons and OSM tag mapping"
```

---

### Task 6: Layout engine (map/layout.py)

**Files:**
- Create: `lake_sticker/map/layout.py`
- Create: `tests/test_map_layout.py`

- [ ] **Step 1: Write failing tests**

`tests/test_map_layout.py`:

```python
"""Tests for lake_sticker.map.layout module."""

from lake_sticker.map.layout import resolve_icon_collisions, build_legend, place_road_labels


def test_resolve_collisions_no_overlap():
    """Icons that don't overlap should stay in place."""
    icons = [
        {"x": 100, "y": 100, "name": "A", "importance": 1},
        {"x": 300, "y": 300, "name": "B", "importance": 1},
    ]
    result = resolve_icon_collisions(icons, icon_size=40, canvas_w=800, canvas_h=600)
    assert len(result) == 2
    # Positions should be unchanged or very close
    assert abs(result[0]["x"] - 100) < 50
    assert abs(result[1]["x"] - 300) < 50


def test_resolve_collisions_overlapping():
    """Overlapping icons should be nudged apart."""
    icons = [
        {"x": 100, "y": 100, "name": "A", "importance": 2},
        {"x": 105, "y": 105, "name": "B", "importance": 1},
    ]
    result = resolve_icon_collisions(icons, icon_size=40, canvas_w=800, canvas_h=600)
    # After resolution, they should not overlap
    dx = abs(result[0]["x"] - result[1]["x"])
    dy = abs(result[0]["y"] - result[1]["y"])
    assert dx >= 30 or dy >= 30  # at least one axis separated


def test_build_legend():
    """build_legend should return numbered entries."""
    pois = [
        {"name": "Town Hall", "icon": "house"},
        {"name": "St. Mary's", "icon": "church"},
        {"name": "Joe's Diner", "icon": "restaurant"},
    ]
    legend = build_legend(pois)
    assert len(legend) == 3
    assert legend[0]["number"] == 1
    assert legend[0]["name"] == "Town Hall"
    assert legend[2]["number"] == 3


def test_place_road_labels():
    """Should only label roads long enough to fit their name."""
    roads = [
        {"name": "Main Street", "smoothed_coords": [(0, 0), (100, 0), (200, 0)]},
        {"name": "A Very Long Road Name That Wont Fit", "smoothed_coords": [(0, 0), (5, 0)]},
        {"name": None, "smoothed_coords": [(0, 0), (50, 0)]},
    ]
    labels = place_road_labels(roads, min_length=50)
    # Only "Main Street" should be labeled (long enough and has a name)
    assert len(labels) == 1
    assert labels[0]["name"] == "Main Street"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_map_layout.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement `map/layout.py`**

`lake_sticker/map/layout.py`:

```python
"""Layout engine for positioning icons and labels on the map."""

import math


def resolve_icon_collisions(icons, icon_size=40, canvas_w=800, canvas_h=600):
    """Resolve overlapping icons using grid-based nudging.

    More important icons stay in place; less important ones are nudged.

    Args:
        icons: list of dicts with x, y, name, importance keys
        icon_size: icon bounding box size in pixels
        canvas_w, canvas_h: canvas dimensions

    Returns:
        List of icon dicts with adjusted x, y positions.
    """
    if not icons:
        return icons

    # Sort by importance (highest first — they get priority placement)
    sorted_icons = sorted(icons, key=lambda i: -i.get("importance", 0))

    placed = []
    half = icon_size / 2

    for icon in sorted_icons:
        x, y = icon["x"], icon["y"]

        # Check for collision with already-placed icons
        for placed_icon in placed:
            dx = abs(x - placed_icon["x"])
            dy = abs(y - placed_icon["y"])
            if dx < icon_size * 0.75 and dy < icon_size * 0.75:
                # Nudge away from the collision
                angle = math.atan2(y - placed_icon["y"], x - placed_icon["x"])
                if angle == 0:
                    angle = math.pi / 4  # avoid zero-angle nudge
                x = placed_icon["x"] + icon_size * math.cos(angle)
                y = placed_icon["y"] + icon_size * math.sin(angle)

        # Clamp to canvas bounds
        x = max(half, min(canvas_w - half, x))
        y = max(half, min(canvas_h - half, y))

        icon["x"] = x
        icon["y"] = y
        placed.append(icon)

    return placed


def build_legend(pois):
    """Build a numbered legend from a list of POIs.

    Args:
        pois: list of dicts with 'name' and 'icon' keys

    Returns:
        List of legend entry dicts with 'number', 'name', 'icon' keys.
    """
    legend = []
    for i, poi in enumerate(pois, 1):
        legend.append({
            "number": i,
            "name": poi.get("name", f"Point {i}"),
            "icon": poi.get("icon", "pin"),
        })
    return legend


def place_road_labels(roads, min_length=50):
    """Determine which roads get labels based on path length.

    Args:
        roads: list of road feature dicts with 'name' and 'smoothed_coords'
        min_length: minimum path length in SVG units to qualify for a label

    Returns:
        List of label dicts with 'name' and 'coords' for textPath placement.
    """
    labels = []
    for road in roads:
        name = road.get("name")
        if not name:
            continue

        coords = road.get("smoothed_coords", [])
        if len(coords) < 2:
            continue

        # Calculate approximate path length
        length = 0
        for i in range(len(coords) - 1):
            dx = coords[i + 1][0] - coords[i][0]
            dy = coords[i + 1][1] - coords[i][1]
            length += math.sqrt(dx * dx + dy * dy)

        if length >= min_length:
            labels.append({"name": name, "coords": coords})

    return labels
```

- [ ] **Step 4: Run all layout tests**

Run: `.venv/bin/pytest tests/test_map_layout.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add lake_sticker/map/layout.py tests/test_map_layout.py
git commit -m "feat: layout engine with icon collision avoidance and label placement"
```

---

## Chunk 4: SVG Rendering + CLI Integration

### Task 7: Map SVG rendering (map/render.py)

**Files:**
- Create: `lake_sticker/map/render.py`
- Create: `tests/test_map_render.py`

- [ ] **Step 1: Write failing tests**

`tests/test_map_render.py`:

```python
"""Tests for lake_sticker.map.render module."""

import xml.etree.ElementTree as ET
from shapely.geometry import LineString, Polygon, Point
from lake_sticker.map.render import generate_map_editable_svg, generate_map_cut_svg


def _sample_processed_features():
    """Create a minimal set of processed features for testing."""
    return {
        "roads": [
            {
                "type": "road",
                "road_class": "primary",
                "name": "Main Street",
                "geometry": LineString([(-71.5, 43.5), (-71.4, 43.5), (-71.3, 43.5)]),
                "smoothed_coords": [(-71.5, 43.5), (-71.45, 43.5), (-71.4, 43.5), (-71.35, 43.5), (-71.3, 43.5)],
                "osm_tags": {"highway": "primary"},
            },
        ],
        "water": [
            {
                "type": "water",
                "name": "Crystal Lake",
                "geometry": Polygon([(-71.5, 43.55), (-71.4, 43.55), (-71.4, 43.65), (-71.5, 43.65), (-71.5, 43.55)]),
                "osm_tags": {"natural": "water"},
            },
        ],
        "green": [],
        "buildings": [],
        "pois": [
            {
                "type": "poi",
                "name": "Town Hall",
                "geometry": Point(-71.45, 43.52),
                "osm_tags": {"amenity": "townhall"},
                "icon": "house",
            },
        ],
    }


def test_editable_svg_has_all_layers():
    """Editable SVG should have named groups for each layer."""
    features = _sample_processed_features()
    svg = generate_map_editable_svg(
        features=features,
        bounds=(-71.55, 43.45, -71.25, 43.7),
        title="TEST TOWN",
        subtitle="NEW HAMPSHIRE",
        colors=None,
        border_style="dotted",
        label_style="none",
    )
    assert '<g id="background">' in svg
    assert '<g id="water">' in svg
    assert '<g id="roads">' in svg
    assert '<g id="icons">' in svg
    assert '<g id="title">' in svg
    assert "viewBox=" in svg


def test_editable_svg_contains_title():
    features = _sample_processed_features()
    svg = generate_map_editable_svg(
        features=features,
        bounds=(-71.55, 43.45, -71.25, 43.7),
        title="WOLFEBORO",
        subtitle="NH",
        colors=None,
        border_style=None,
        label_style="none",
    )
    assert "WOLFEBORO" in svg


def test_editable_svg_valid_xml():
    features = _sample_processed_features()
    svg = generate_map_editable_svg(
        features=features,
        bounds=(-71.55, 43.45, -71.25, 43.7),
        title="TEST",
        subtitle="",
        colors=None,
        border_style=None,
        label_style="none",
    )
    ET.fromstring(svg)


def test_cut_svg_has_no_map_content():
    """Cut SVG should only have the border outline, no map content."""
    features = _sample_processed_features()
    svg = generate_map_cut_svg(
        bounds=(-71.55, 43.45, -71.25, 43.7),
        border_style="dotted",
        colors=None,
    )
    assert "<text" not in svg
    assert "roads" not in svg.lower() or '<g id="roads">' not in svg


def test_cut_svg_valid_xml():
    svg = generate_map_cut_svg(
        bounds=(-71.55, 43.45, -71.25, 43.7),
        border_style="double_line",
        colors=None,
    )
    ET.fromstring(svg)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_map_render.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement `map/render.py`**

`lake_sticker/map/render.py`:

```python
"""SVG composition for map stickers.

Composes processed map features, icons, labels, and borders into
editable and cut-ready SVG documents.
"""

from lake_sticker.geometry import compute_projection, coords_to_svg_path
from lake_sticker.borders import RECT_BORDER_STYLES
from lake_sticker.map.icons import load_icon_mapping, resolve_icon, load_icon_svg
from lake_sticker.map.layout import resolve_icon_collisions, build_legend, place_road_labels

CANVAS_WIDTH = 800
PADDING = 60
LABEL_FONT = "Georgia, 'Times New Roman', serif"

DEFAULT_COLORS = {
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

ROAD_WIDTHS = {
    "primary": (10, 7),      # (outline, fill) widths
    "secondary": (7, 5),
    "residential": (5, 3),
    "footway": (0, 1.5),
}


def _merge_colors(user_colors):
    """Merge user color overrides with defaults."""
    colors = dict(DEFAULT_COLORS)
    if user_colors:
        # Map simplified CLI keys to internal keys
        key_map = {
            "water": "water",
            "roads": "road_fill",
            "green": "green",
            "buildings": "building",
            "labels": "label",
        }
        for cli_key, internal_key in key_map.items():
            if cli_key in user_colors:
                colors[internal_key] = user_colors[cli_key]
    return colors


def _compute_map_canvas(bounds, has_title, has_border):
    """Compute canvas dimensions from geographic bounds."""
    min_lon, min_lat, max_lon, max_lat = bounds
    aspect = (max_lat - min_lat) / (max_lon - min_lon) if (max_lon - min_lon) > 0 else 1
    canvas_w = CANVAS_WIDTH
    canvas_h = int(canvas_w * aspect) + 2 * PADDING
    title_space = 80 if has_title else 0
    border_margin = 30 if has_border else 0
    total_h = canvas_h + title_space + border_margin
    return canvas_w, canvas_h, total_h, border_margin


def _render_water(features, bounds, canvas_w, canvas_h, padding, colors):
    """Render water features as SVG paths with decorative wave lines."""
    import random
    parts = ['  <g id="water">']
    project = compute_projection(bounds, canvas_w, canvas_h, padding)
    for f in features.get("water", []):
        geom = f["geometry"]
        if geom.geom_type == "Polygon":
            coords = list(geom.exterior.coords)
            path_d = coords_to_svg_path(coords, bounds, canvas_w, canvas_h, padding)
            parts.append(f'    <path fill="{colors["water"]}" stroke="none" d="{path_d}"/>')
            # Add decorative wave lines inside the polygon
            minx, miny, maxx, maxy = geom.bounds
            wave_y = miny + (maxy - miny) * 0.3
            while wave_y < maxy - (maxy - miny) * 0.2:
                x1, y1 = project(minx + (maxx - minx) * 0.15, wave_y)
                x2, y2 = project(maxx - (maxx - minx) * 0.15, wave_y)
                mid_x = (x1 + x2) / 2
                cp_y = y1 - 4  # slight curve
                parts.append(
                    f'    <path d="M {x1:.0f},{y1:.0f} Q {mid_x:.0f},{cp_y:.0f} {x2:.0f},{y2:.0f}" '
                    f'fill="none" stroke="{colors["water_waves"]}" stroke-width="1.5" opacity="0.6"/>'
                )
                wave_y += (maxy - miny) * 0.15
        elif geom.geom_type == "LineString":
            coords = list(geom.coords)
            path_d = coords_to_svg_path(coords, bounds, canvas_w, canvas_h, padding, close=False)
            parts.append(f'    <path fill="none" stroke="{colors["water"]}" stroke-width="3" d="{path_d}"/>')
    parts.append("  </g>")
    return "\n".join(parts)


def _render_green(features, bounds, canvas_w, canvas_h, padding, colors):
    """Render green space polygons with scattered tree icons."""
    import random
    parts = ['  <g id="green-spaces">']
    project = compute_projection(bounds, canvas_w, canvas_h, padding)
    for f in features.get("green", []):
        geom = f["geometry"]
        if geom.geom_type == "Polygon":
            coords = list(geom.exterior.coords)
            path_d = coords_to_svg_path(coords, bounds, canvas_w, canvas_h, padding)
            parts.append(f'    <path fill="{colors["green"]}" fill-opacity="0.3" stroke="none" d="{path_d}"/>')
            # Scatter small tree circles inside the polygon
            minx, miny, maxx, maxy = geom.bounds
            area = geom.area
            num_trees = min(20, max(3, int(area * 500000)))  # scale with area
            rng = random.Random(42)  # deterministic for reproducibility
            for _ in range(num_trees * 3):  # oversample, filter by containment
                px = rng.uniform(minx, maxx)
                py = rng.uniform(miny, maxy)
                from shapely.geometry import Point as SPoint
                if geom.contains(SPoint(px, py)):
                    sx, sy = project(px, py)
                    r = rng.uniform(3, 6)
                    parts.append(
                        f'    <circle cx="{sx:.0f}" cy="{sy:.0f}" r="{r:.0f}" '
                        f'fill="{colors["green"]}" fill-opacity="0.7" stroke="none"/>'
                    )
                    num_trees -= 1
                    if num_trees <= 0:
                        break
    parts.append("  </g>")
    return "\n".join(parts)


def _render_roads(features, bounds, canvas_w, canvas_h, padding, colors):
    """Render roads with two-stroke technique for illustrated look."""
    parts = ['  <g id="roads">']
    for f in features.get("roads", []):
        road_class = f.get("road_class", "residential")
        outline_w, fill_w = ROAD_WIDTHS.get(road_class, (5, 3))
        coords = f.get("smoothed_coords", list(f["geometry"].coords))
        path_d = coords_to_svg_path(coords, bounds, canvas_w, canvas_h, padding, close=False)

        if outline_w > 0:
            parts.append(
                f'    <path fill="none" stroke="{colors["road_outline"]}" '
                f'stroke-width="{outline_w}" stroke-linecap="round" stroke-linejoin="round" d="{path_d}"/>'
            )
        dash = ' stroke-dasharray="4 3"' if road_class == "footway" else ""
        parts.append(
            f'    <path fill="none" stroke="{colors["road_fill"]}" '
            f'stroke-width="{fill_w}" stroke-linecap="round" stroke-linejoin="round"{dash} d="{path_d}"/>'
        )
    parts.append("  </g>")
    return "\n".join(parts)


def _render_buildings(features, bounds, canvas_w, canvas_h, padding, colors):
    """Render building footprints as simplified rectangles."""
    parts = ['  <g id="buildings">']
    project = compute_projection(bounds, canvas_w, canvas_h, padding)
    for f in features.get("buildings", []):
        geom = f["geometry"]
        if geom.geom_type == "Polygon":
            minx, miny, maxx, maxy = geom.bounds
            x1, y1 = project(minx, maxy)
            x2, y2 = project(maxx, miny)
            w = abs(x2 - x1)
            h = abs(y2 - y1)
            parts.append(
                f'    <rect x="{min(x1, x2):.1f}" y="{min(y1, y2):.1f}" '
                f'width="{w:.1f}" height="{h:.1f}" rx="1" '
                f'fill="{colors["building"]}" fill-opacity="0.7" stroke="none"/>'
            )
    parts.append("  </g>")
    return "\n".join(parts)


def _render_icons(features, bounds, canvas_w, canvas_h, padding):
    """Render POI icons using defs+use pattern."""
    mapping = load_icon_mapping()
    project = compute_projection(bounds, canvas_w, canvas_h, padding)

    # Resolve icons and compute positions
    icon_instances = []
    used_icons = set()
    for f in features.get("pois", []):
        icon_name = f.get("icon") or resolve_icon(f["osm_tags"], mapping)
        geom = f["geometry"]
        if geom.geom_type == "Point":
            x, y = project(geom.x, geom.y)
        else:
            centroid = geom.centroid
            x, y = project(centroid.x, centroid.y)

        used_icons.add(icon_name)
        icon_instances.append({
            "x": x, "y": y,
            "name": f.get("name", ""),
            "icon": icon_name,
            "importance": 1,
        })

    # Resolve collisions
    icon_instances = resolve_icon_collisions(icon_instances, icon_size=30, canvas_w=canvas_w, canvas_h=canvas_h)

    # Build defs
    defs_parts = ["  <defs>"]
    for icon_name in sorted(used_icons):
        try:
            svg_content = load_icon_svg(icon_name)
            defs_parts.append(f'    <g id="icon-{icon_name}">{svg_content}</g>')
        except FileNotFoundError:
            pass
    defs_parts.append("  </defs>")

    # Build use instances
    icon_parts = ['  <g id="icons">']
    for inst in icon_instances:
        icon_name = inst["icon"]
        x, y = inst["x"], inst["y"]
        icon_parts.append(
            f'    <use href="#icon-{icon_name}" x="{x - 15:.1f}" y="{y - 15:.1f}" width="30" height="30"/>'
        )
    icon_parts.append("  </g>")

    return "\n".join(defs_parts), "\n".join(icon_parts), icon_instances


def _render_title(title, subtitle, canvas_w, canvas_h, border_margin, colors):
    """Render title and subtitle text."""
    parts = ['  <g id="title">']
    center_x = canvas_w // 2
    title_y = canvas_h + border_margin + 35
    parts.append(
        f'    <text x="{center_x}" y="{title_y}" text-anchor="middle" '
        f'font-family="{LABEL_FONT}" font-weight="700" font-size="28" '
        f'fill="{colors["title"]}" letter-spacing="3">{title}</text>'
    )
    if subtitle:
        parts.append(
            f'    <text x="{center_x}" y="{title_y + 28}" text-anchor="middle" '
            f'font-family="{LABEL_FONT}" font-weight="400" font-size="14" '
            f'fill="{colors["title"]}" letter-spacing="5">{subtitle}</text>'
        )
    parts.append("  </g>")
    return "\n".join(parts)


def generate_map_editable_svg(features, bounds, title, subtitle,
                               colors, border_style, label_style):
    """Generate an editable map SVG with named layer groups.

    Args:
        features: processed features dict from features.py
        bounds: (min_lon, min_lat, max_lon, max_lat)
        title: map title text
        subtitle: subtitle text
        colors: user color overrides dict (or None for defaults)
        border_style: "dotted", "double_line", "dashed", or None
        label_style: "major", "legend", "selective", "none"

    Returns:
        Complete SVG document string.
    """
    colors = _merge_colors(colors)
    has_title = bool(title)
    has_border = border_style is not None
    canvas_w, canvas_h, total_h, border_margin = _compute_map_canvas(bounds, has_title, has_border)

    map_padding = PADDING + (border_margin // 2 if has_border else 0)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {canvas_w} {total_h}" width="{canvas_w}" height="{total_h}">',
        f'  <!-- Generated from OpenStreetMap data. (c) OpenStreetMap contributors -->',
    ]

    # Background
    parts.append(f'  <g id="background">')
    parts.append(f'    <rect width="{canvas_w}" height="{total_h}" fill="{colors["background"]}"/>')
    parts.append(f'  </g>')

    # Map layers
    parts.append(_render_green(features, bounds, canvas_w, canvas_h, map_padding, colors))
    parts.append(_render_water(features, bounds, canvas_w, canvas_h, map_padding, colors))
    parts.append(_render_roads(features, bounds, canvas_w, canvas_h, map_padding, colors))
    parts.append(_render_buildings(features, bounds, canvas_w, canvas_h, map_padding, colors))

    # Icons
    defs_svg, icons_svg, icon_instances = _render_icons(features, bounds, canvas_w, canvas_h, map_padding)
    parts.append(defs_svg)
    parts.append(icons_svg)

    # Labels (simplified — only "none" and "legend" for v1)
    if label_style == "legend" and icon_instances:
        legend_entries = build_legend([
            {"name": i["name"], "icon": i["icon"]}
            for i in icon_instances if i.get("name")
        ])
        if legend_entries:
            parts.append('  <g id="legend">')
            legend_x = canvas_w - 180
            legend_y = map_padding + 20
            for entry in legend_entries[:15]:  # max 15 entries
                parts.append(
                    f'    <circle cx="{legend_x}" cy="{legend_y}" r="8" '
                    f'fill="{colors["label"]}" stroke="none"/>'
                )
                parts.append(
                    f'    <text x="{legend_x}" y="{legend_y + 4}" text-anchor="middle" '
                    f'font-family="{LABEL_FONT}" font-size="10" fill="white" '
                    f'font-weight="bold">{entry["number"]}</text>'
                )
                parts.append(
                    f'    <text x="{legend_x + 15}" y="{legend_y + 4}" '
                    f'font-family="{LABEL_FONT}" font-size="10" '
                    f'fill="{colors["label"]}">{entry["name"]}</text>'
                )
                legend_y += 20
            parts.append('  </g>')

    # Title
    if has_title:
        parts.append(_render_title(title, subtitle, canvas_w, canvas_h, border_margin, colors))

    # Border (rendered on top of map content, per spec layer ordering)
    if has_border and border_style in RECT_BORDER_STYLES:
        border_fn = RECT_BORDER_STYLES[border_style]
        parts.append(border_fn(
            x=border_margin / 2, y=border_margin / 2,
            w=canvas_w - border_margin, h=total_h - border_margin,
            color=colors["label"],
        ))

    parts.append("</svg>")
    return "\n".join(parts)


def generate_map_cut_svg(bounds, border_style, colors):
    """Generate a cut-ready SVG with just the sticker border outline.

    Args:
        bounds: (min_lon, min_lat, max_lon, max_lat)
        border_style: "dotted", "double_line", "dashed", or None
        colors: user color overrides (or None)

    Returns:
        SVG document string with only the cut border.
    """
    colors = _merge_colors(colors)
    canvas_w, canvas_h, total_h, border_margin = _compute_map_canvas(bounds, has_title=False, has_border=True)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {total_h}" '
        f'width="{canvas_w}" height="{total_h}">',
    ]

    if border_style and border_style in RECT_BORDER_STYLES:
        border_fn = RECT_BORDER_STYLES[border_style]
        parts.append(border_fn(
            x=border_margin / 2, y=border_margin / 2,
            w=canvas_w - border_margin, h=total_h - border_margin,
            color=colors["label"],
            cut_ready=True,
        ))
    else:
        # Default: simple rectangle outline
        parts.append(
            f'  <rect x="5" y="5" width="{canvas_w - 10}" height="{total_h - 10}" '
            f'rx="15" fill="none" stroke="{colors["label"]}" stroke-width="1"/>'
        )

    parts.append("</svg>")
    return "\n".join(parts)
```

- [ ] **Step 4: Run all render tests**

Run: `.venv/bin/pytest tests/test_map_render.py -v`
Expected: 5 passed

- [ ] **Step 5: Run full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add lake_sticker/map/render.py tests/test_map_render.py
git commit -m "feat: map SVG rendering with layered composition"
```

---

### Task 8: Map CLI prompts (map/cli.py)

**Files:**
- Create: `lake_sticker/map/cli.py`

- [ ] **Step 1: Implement `map/cli.py`**

`lake_sticker/map/cli.py`:

```python
"""Map-specific interactive CLI prompts."""

from lake_sticker.search import search_location, sanitize_filename, SearchError
from lake_sticker.map.fetch import fetch_map_data
from lake_sticker.map.features import process_map_features
from lake_sticker.map.render import generate_map_editable_svg, generate_map_cut_svg

# Import shared CLI helpers from main cli module
from lake_sticker.cli import _input_with_default, _input_int, _input_yes_no, _unique_path, OUTPUT_DIR

DEFAULT_COLORS = {
    "water": "#7eb8cc",
    "roads": "#c9b88a",
    "green": "#5a8f4a",
    "buildings": "#d4816b",
    "labels": "#3d405b",
}

RADIUS_OPTIONS = {
    1: ("Small (few blocks, ~500m)", 500),
    2: ("Medium (neighborhood, ~1km)", 1000),
    3: ("Large (town center, ~2km)", 2000),
}


def step_search_location():
    """Search for a location and return the selected candidate."""
    while True:
        query = input("\nEnter location (town, city, or address): ").strip()
        if not query:
            continue

        print("\nSearching OpenStreetMap...")
        try:
            candidates = search_location(query)
        except SearchError as e:
            print(f"  Error: {e}")
            continue

        if not candidates:
            print("  No results found. Try a different name or be more specific.")
            continue

        if len(candidates) == 1:
            c = candidates[0]
            print(f"  Found: {c['name']} -- {c['location_display']}")
            if _input_yes_no("  Use this?", default=True):
                return c
            continue

        display_count = min(len(candidates), 15)
        print(f"Found {len(candidates)} results:\n")
        for i, c in enumerate(candidates[:display_count], 1):
            print(f"  {i}) {c['name']} -- {c['location_display']}")
        if len(candidates) > 15:
            print(f"\n  (Showing 15 of {len(candidates)}. Be more specific to narrow results.)")

        idx = _input_int(f"\nSelect a location [1-{display_count}]: ", 1, display_count)
        return candidates[idx - 1]


def step_configure_map(candidate, raw_features):
    """Configure map options: area, categories, labels, border, colors."""
    config = {
        "center": (candidate["lat"], candidate["lon"]),
    }

    # Categorize features for the toggle display
    category_counts = {}
    category_names = {
        "water": "Water (lakes, rivers)",
        "roads": "Roads (main streets, paths)",
        "green": "Green spaces (parks, forests)",
        "buildings": "Buildings (houses, shops)",
        "landmarks": "Landmarks (churches, museums)",
        "recreation": "Recreation (marinas, beaches)",
        "food_drink": "Food & drink (restaurants, cafes)",
    }

    # Count features by category
    for f in raw_features:
        ft = f["type"]
        if ft == "road":
            category_counts["roads"] = category_counts.get("roads", 0) + 1
        elif ft == "water":
            category_counts["water"] = category_counts.get("water", 0) + 1
        elif ft == "green":
            category_counts["green"] = category_counts.get("green", 0) + 1
        elif ft == "building":
            category_counts["buildings"] = category_counts.get("buildings", 0) + 1
        elif ft == "poi":
            tags = f.get("osm_tags", {})
            if any(k in tags for k in ("amenity", "tourism", "historic")):
                if any(tags.get(k) in ("restaurant", "cafe", "bar", "pub", "fast_food") for k in tags):
                    category_counts["food_drink"] = category_counts.get("food_drink", 0) + 1
                elif any(tags.get(k) in ("marina", "beach_resort") for k in tags):
                    category_counts["recreation"] = category_counts.get("recreation", 0) + 1
                else:
                    category_counts["landmarks"] = category_counts.get("landmarks", 0) + 1
            elif "shop" in tags:
                category_counts["landmarks"] = category_counts.get("landmarks", 0) + 1

    # Default: enable categories that have data
    categories = {k: (k in category_counts) for k in category_names}

    # Show categories
    print("\nFeature categories to include:")
    cat_list = list(category_names.keys())
    for i, key in enumerate(cat_list, 1):
        check = "x" if categories[key] else " "
        count = category_counts.get(key, 0)
        label = category_names[key]
        print(f"  {i}. [{check}] {label} ({count})")

    if _input_yes_no("Toggle categories?", default=False):
        toggle_input = input("  Toggle which? (comma-separated numbers): ").strip()
        try:
            indices = [int(x.strip()) for x in toggle_input.split(",")]
            for idx in indices:
                if 1 <= idx <= len(cat_list):
                    key = cat_list[idx - 1]
                    categories[key] = not categories[key]
        except ValueError:
            print("  Invalid input, keeping defaults.")

    config["categories"] = categories

    # Label style (v1: legend and none; major/selective coming later)
    print("\nLabel style:")
    print("  1) Labels + numbered legend")
    print("  2) No labels")
    label_choice = _input_int("Select [1-2]: ", 1, 2)
    label_map = {1: "legend", 2: "none"}
    config["label_style"] = label_map[label_choice]

    # Border style
    print("\nBorder style:")
    print("  1) Dotted border")
    print("  2) Double-line frame")
    print("  3) Dashed border")
    print("  4) None")
    border_choice = _input_int("Select border [1-4]: ", 1, 4)
    border_map = {1: "dotted", 2: "double_line", 3: "dashed", 4: None}
    config["border_style"] = border_map[border_choice]

    # Colors
    print("\nColors:")
    config["colors"] = {}
    for key, default in DEFAULT_COLORS.items():
        config["colors"][key] = _input_with_default(key.replace("_", " ").title(), default)

    # Title
    name = candidate["name"].upper()
    location_parts = candidate["location_display"].split(", ")
    subtitle = location_parts[-1].upper() if location_parts else ""

    print(f"\nTitle: {name}")
    print(f"Subtitle: {subtitle}")
    if _input_yes_no("Edit title?", default=False):
        name = _input_with_default("Title", name)
        subtitle = _input_with_default("Subtitle", subtitle)

    config["title"] = name
    config["subtitle"] = subtitle

    return config


def step_generate_map(candidate, config, raw_features):
    """Process features and generate map SVG files."""
    # Process features
    processed = process_map_features(raw_features)

    # Compute bounds from all feature geometries
    all_coords = []
    for category in processed.values():
        for f in category:
            geom = f["geometry"]
            if hasattr(geom, "bounds"):
                minx, miny, maxx, maxy = geom.bounds
                all_coords.extend([(minx, miny), (maxx, maxy)])

    if not all_coords:
        print("  No features to render.")
        return False

    lons = [c[0] for c in all_coords]
    lats = [c[1] for c in all_coords]
    margin = 0.005
    bounds = (min(lons) - margin, min(lats) - margin, max(lons) + margin, max(lats) + margin)

    # Generate SVGs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_filename(candidate["name"], candidate["location_display"]) + "_map"

    editable_path = _unique_path(OUTPUT_DIR / f"{base_name}_editable.svg")
    cut_path = _unique_path(OUTPUT_DIR / f"{base_name}_cut.svg")

    print("\nGenerating map sticker...")

    editable_svg = generate_map_editable_svg(
        features=processed,
        bounds=bounds,
        title=config["title"],
        subtitle=config["subtitle"],
        colors=config.get("colors"),
        border_style=config["border_style"],
        label_style=config["label_style"],
    )
    cut_svg = generate_map_cut_svg(
        bounds=bounds,
        border_style=config["border_style"],
        colors=config.get("colors"),
    )

    editable_path.write_text(editable_svg)
    cut_path.write_text(cut_svg)

    print(f"  > {editable_path}  (layered, editable)")
    print(f"  > {cut_path}  (cut outline)")
    print(f"\nDone! Open the editable SVG in Inkscape/Illustrator for final touches.")
    return True


def run_map_flow():
    """Run the complete map sticker generation flow."""
    candidate = step_search_location()

    # Area size
    print("\nMap area:")
    for key, (label, _) in RADIUS_OPTIONS.items():
        print(f"  {key}) {label}")
    print("  4) Custom radius")
    area_choice = _input_int("Select [1-4]: ", 1, 4)

    if area_choice in RADIUS_OPTIONS:
        radius = RADIUS_OPTIONS[area_choice][1]
    else:
        custom = input("  Radius in meters [2000]: ").strip()
        try:
            radius = int(custom) if custom else 2000
        except ValueError:
            radius = 2000

    # Fetch data
    print(f"\nFetching map data for {candidate['name']} ({candidate['location_display']})...")
    try:
        raw_features = fetch_map_data(lat=candidate["lat"], lon=candidate["lon"], radius=radius)
    except RuntimeError as e:
        print(f"  Error: {e}")
        return

    # Show counts
    type_counts = {}
    for f in raw_features:
        type_counts[f["type"]] = type_counts.get(f["type"], 0) + 1
    for ft, count in sorted(type_counts.items()):
        print(f"  {ft.title()}: {count}")

    if len(raw_features) < 5:
        print("  Warning: very few features found. Consider increasing the radius.")

    config = step_configure_map(candidate, raw_features)
    step_generate_map(candidate, config, raw_features)
```

- [ ] **Step 2: Run existing tests to verify no regressions**

Run: `.venv/bin/pytest tests/ -v`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add lake_sticker/map/cli.py
git commit -m "feat: map-specific CLI prompts and generation flow"
```

---

### Task 9: Integrate mode selector into main CLI

**Files:**
- Modify: `lake_sticker/cli.py`

- [ ] **Step 1: Modify `main()` in `cli.py` to add mode selector**

Replace the `main()` function in `lake_sticker/cli.py`:

```python
def main():
    """Main entry point for the Lake Sticker Maker CLI."""
    print("\nLake Sticker Maker")
    print("=" * 22)

    while True:
        print("\nWhat would you like to create?")
        print("  1) Lake sticker")
        print("  2) Map sticker")
        mode = _input_int("Select [1-2]: ", 1, 2)

        if mode == 1:
            # Existing lake sticker flow
            candidate = _step_search()
            config = _step_configure(candidate)
            _step_generate(candidate, config)
        else:
            # Map sticker flow
            from lake_sticker.map.cli import run_map_flow
            run_map_flow()

        if not _input_yes_no("\nGenerate another?", default=False):
            break

    print("\nGoodbye!")
```

- [ ] **Step 2: Run all tests**

Run: `.venv/bin/pytest tests/ -v`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add lake_sticker/cli.py
git commit -m "feat: add mode selector (lake sticker / map sticker) to main CLI"
```

---

### Task 10: Integration testing

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 2: Manual smoke test**

Run: `.venv/bin/python run.py`

1. Select "Map sticker"
2. Search for "Wolfeboro, NH"
3. Pick "Large (town center, ~2km)"
4. Accept default categories
5. Pick "Labels + numbered legend"
6. Pick "Double-line frame" border
7. Accept default colors
8. Verify two SVGs generated in `output/`
9. Open the editable SVG in a browser — verify layers are visible

- [ ] **Step 3: Test lake sticker mode still works**

1. Select "Lake sticker"
2. Search "Lake Winnipesaukee"
3. Accept defaults
4. Verify SVGs generated correctly

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: whimsical map sticker v1 — complete with icons, layout, and rendering"
```
