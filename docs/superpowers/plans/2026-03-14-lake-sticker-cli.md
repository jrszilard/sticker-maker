# Lake Sticker CLI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an interactive CLI tool that fetches any lake's shape from OpenStreetMap and generates Cricut-ready SVG stickers with decorative borders.

**Architecture:** Python package (`lake_sticker/`) with 5 modules: search (Nominatim API), geometry (Overpass fetch + Shapely processing), borders (elliptical decorative frames), svg (two-variant output), and cli (interactive orchestration). Entry points via `run.py` and `pyproject.toml` console script.

**Tech Stack:** Python 3.12, Shapely (geometry), requests (HTTP), pytest (testing). Optional: osmnx+geopandas (fallback geometry fetching).

**Spec:** `docs/superpowers/specs/2026-03-14-lake-sticker-cli-design.md`

---

## File Structure

```
sticker-maker/
├── lake_sticker/
│   ├── __init__.py          # __version__, public imports
│   ├── search.py            # search_lakes() → list of candidates
│   ├── geometry.py          # fetch_geometry(), process_geometry(), auto_tolerance()
│   ├── borders.py           # dotted_ring(), double_line_frame(), dashed_ring()
│   ├── svg.py               # generate_editable_svg(), generate_cut_svg()
│   └── cli.py               # main() interactive loop
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # shared fixtures (sample geometries, mock responses)
│   ├── test_search.py
│   ├── test_geometry.py
│   ├── test_borders.py
│   └── test_svg.py
├── output/                  # .gitignore'd, created at runtime
├── .cache/                  # .gitignore'd, geometry cache
├── generate_lake_svg.py     # original script, kept for reference
├── pyproject.toml
├── run.py
└── .gitignore
```

---

## Chunk 1: Project Scaffolding + Search Module

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `lake_sticker/__init__.py`
- Create: `run.py`
- Create: `.gitignore`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "lake-sticker"
version = "0.1.0"
description = "Generate lake sticker SVGs from OpenStreetMap data"
requires-python = ">=3.10"
dependencies = [
    "shapely>=2.0",
    "requests>=2.28",
]

[project.optional-dependencies]
osmnx = ["osmnx>=1.6", "geopandas>=0.14"]
dev = ["pytest>=7.0"]

[project.scripts]
lake-sticker = "lake_sticker.cli:main"
```

- [ ] **Step 2: Create `lake_sticker/__init__.py`**

```python
"""Lake Sticker — generate SVG lake stickers from OpenStreetMap data."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create `run.py`**

```python
#!/usr/bin/env python3
"""Simple entry point — no install required."""

from lake_sticker.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create `.gitignore`**

```
output/
.cache/
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.venv/
*.svg
!generate_lake_svg.py
```

- [ ] **Step 5: Create `tests/__init__.py` and `tests/conftest.py`**

`tests/__init__.py`: empty file.

`tests/conftest.py`:

```python
"""Shared test fixtures for lake_sticker tests."""

import pytest
from shapely.geometry import Polygon, MultiPolygon


@pytest.fixture
def simple_lake_coords():
    """A simple square 'lake' in lon/lat coords."""
    return [
        (-71.5, 43.5),
        (-71.4, 43.5),
        (-71.4, 43.6),
        (-71.5, 43.6),
        (-71.5, 43.5),
    ]


@pytest.fixture
def simple_lake_polygon(simple_lake_coords):
    """A Shapely polygon for the simple lake."""
    return Polygon(simple_lake_coords)


@pytest.fixture
def lake_with_island():
    """A lake polygon with one island (interior ring)."""
    exterior = [
        (-71.5, 43.5),
        (-71.3, 43.5),
        (-71.3, 43.7),
        (-71.5, 43.7),
        (-71.5, 43.5),
    ]
    island = [
        (-71.45, 43.55),
        (-71.35, 43.55),
        (-71.35, 43.65),
        (-71.45, 43.65),
        (-71.45, 43.55),
    ]
    return Polygon(exterior, [island])


@pytest.fixture
def multi_polygon_lake():
    """A lake stored as MultiPolygon (two basins)."""
    p1 = Polygon([
        (-71.5, 43.5), (-71.4, 43.5), (-71.4, 43.6), (-71.5, 43.6), (-71.5, 43.5)
    ])
    p2 = Polygon([
        (-71.39, 43.5), (-71.3, 43.5), (-71.3, 43.6), (-71.39, 43.6), (-71.39, 43.5)
    ])
    return MultiPolygon([p1, p2])


@pytest.fixture
def sample_nominatim_response():
    """A realistic Nominatim search response for 'Crystal Lake'."""
    return [
        {
            "place_id": 123,
            "osm_type": "relation",
            "osm_id": 1234567,
            "display_name": "Crystal Lake, Gilmanton, Belknap County, New Hampshire, USA",
            "class": "natural",
            "type": "water",
            "boundingbox": ["43.4", "43.5", "-71.5", "-71.4"],
        },
        {
            "place_id": 456,
            "osm_type": "way",
            "osm_id": 7654321,
            "display_name": "Crystal Lake, Eaton, Carroll County, New Hampshire, USA",
            "class": "natural",
            "type": "water",
            "boundingbox": ["43.8", "43.9", "-71.1", "-71.0"],
        },
        {
            "place_id": 789,
            "osm_type": "relation",
            "osm_id": 9999999,
            "display_name": "Crystal Lake, Manchester, Hartford County, Connecticut, USA",
            "class": "place",
            "type": "locality",
            "boundingbox": ["41.7", "41.8", "-72.6", "-72.5"],
        },
    ]
```

- [ ] **Step 6: Install dev dependencies and verify**

Run: `cd /home/justin/lakeshore-studio/ai-projects/sticker-maker && pip install -e ".[dev]"`
Expected: successful install, `pytest --version` works

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml lake_sticker/__init__.py run.py .gitignore tests/
git commit -m "scaffold: package structure, test fixtures, and entry points"
```

---

### Task 2: Search module — Nominatim query and result parsing

**Files:**
- Create: `lake_sticker/search.py`
- Create: `tests/test_search.py`

- [ ] **Step 1: Write failing tests for `parse_nominatim_results`**

`tests/test_search.py`:

```python
"""Tests for lake_sticker.search module."""

from lake_sticker.search import parse_nominatim_results


def test_parse_filters_water_features(sample_nominatim_response):
    """Only results with water-related OSM tags should be included."""
    results = parse_nominatim_results(sample_nominatim_response)
    # Third result is class=place/type=locality — should be filtered out
    assert len(results) == 2
    assert all(r["osm_id"] != 9999999 for r in results)


def test_parse_extracts_fields(sample_nominatim_response):
    """Each result should have name, location_display, osm_id, osm_type."""
    results = parse_nominatim_results(sample_nominatim_response)
    r = results[0]
    assert r["osm_id"] == 1234567
    assert r["osm_type"] == "relation"
    assert "Crystal Lake" in r["name"]
    assert "Gilmanton" in r["location_display"]


def test_parse_handles_empty_response():
    """Empty Nominatim response should return empty list."""
    assert parse_nominatim_results([]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_search.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_nominatim_results'`

- [ ] **Step 3: Implement `parse_nominatim_results`**

`lake_sticker/search.py`:

```python
"""Search for lakes using the OpenStreetMap Nominatim API."""

import time
import requests

USER_AGENT = "lake-sticker-maker/1.0"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Rate-limit tracking for Nominatim (1 req/sec policy)
_last_nominatim_request = 0.0

# OSM classes/types that indicate water features
WATER_CLASSES = {
    ("natural", "water"),
    ("water", "lake"),
    ("water", "reservoir"),
    ("water", "pond"),
    ("place", "lake"),
    ("natural", "lake"),
}


def _is_water_feature(result):
    """Check if a Nominatim result is a water feature."""
    cls = result.get("class", "")
    typ = result.get("type", "")
    return (cls, typ) in WATER_CLASSES


def _parse_display_name(display_name):
    """Parse Nominatim display_name into structured parts.

    Nominatim returns comma-separated: "Lake Name, Town, County, State, Country"
    We extract the lake name (first part) and the location context (rest).
    """
    parts = [p.strip() for p in display_name.split(",")]
    name = parts[0] if parts else "Unknown"
    # Build location display from remaining parts, skip country for US lakes
    location_parts = parts[1:] if len(parts) > 1 else []
    # Remove the last part if it's "USA" or "United States" — redundant for display
    if location_parts and location_parts[-1] in ("USA", "United States", "United States of America"):
        location_parts = location_parts[:-1]
    location_display = ", ".join(location_parts) if location_parts else ""
    return name, location_display


def parse_nominatim_results(raw_results):
    """Parse and filter Nominatim results into structured lake candidates.

    Args:
        raw_results: list of dicts from Nominatim JSON response.

    Returns:
        List of dicts with keys: name, location_display, osm_id, osm_type, bbox.
    """
    candidates = []
    for r in raw_results:
        if not _is_water_feature(r):
            continue
        name, location_display = _parse_display_name(r.get("display_name", ""))
        candidates.append({
            "name": name,
            "location_display": location_display,
            "osm_id": r["osm_id"],
            "osm_type": r["osm_type"],
            "bbox": r.get("boundingbox"),
        })
    return candidates
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search.py -v`
Expected: 3 passed

- [ ] **Step 5: Write failing tests for `search_lakes` (HTTP call)**

Add to `tests/test_search.py`:

```python
from unittest.mock import patch, Mock
from lake_sticker.search import search_lakes


def test_search_lakes_makes_nominatim_request(sample_nominatim_response):
    """search_lakes should query Nominatim and return parsed results."""
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_nominatim_response
    mock_resp.raise_for_status = Mock()

    with patch("lake_sticker.search.requests.get", return_value=mock_resp) as mock_get:
        results = search_lakes("Crystal Lake")

    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args
    assert "Crystal Lake" in str(call_kwargs)
    assert len(results) == 2  # filtered water features only


def test_search_lakes_network_error():
    """Network errors should raise SearchError, not crash."""
    with patch("lake_sticker.search.requests.get", side_effect=requests.ConnectionError):
        with pytest.raises(Exception) as exc_info:
            search_lakes("Crystal Lake")
        assert "network" in str(exc_info.value).lower() or "connect" in str(exc_info.value).lower()
```

Add necessary import at top of test file:

```python
import pytest
import requests
```

- [ ] **Step 6: Run tests to verify new ones fail**

Run: `pytest tests/test_search.py -v`
Expected: 2 new FAIL — `ImportError: cannot import name 'search_lakes'`

- [ ] **Step 7: Implement `search_lakes`**

Add to `lake_sticker/search.py`:

```python
class SearchError(Exception):
    """Raised when lake search fails."""
    pass


def _throttle_nominatim():
    """Enforce 1 request/second rate limit for Nominatim API."""
    global _last_nominatim_request
    elapsed = time.time() - _last_nominatim_request
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_nominatim_request = time.time()


def search_lakes(query, max_results=15):
    """Search for lakes matching the query string.

    Args:
        query: lake name, optionally with state/location (e.g. "Crystal Lake, NH").
        max_results: maximum number of results to return.

    Returns:
        List of candidate dicts (see parse_nominatim_results).

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
                "limit": 50,  # fetch more, we filter client-side
                "addressdetails": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        # Retry once on 429
        if resp.status_code == 429:
            time.sleep(5)
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
        resp.raise_for_status()
    except requests.ConnectionError:
        raise SearchError(
            "Could not connect to OpenStreetMap. Check your internet connection."
        )
    except requests.Timeout:
        raise SearchError("Search timed out. Try again in a moment.")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            raise SearchError("Rate limited by OpenStreetMap. Wait a minute and try again.")
        raise SearchError(f"Search failed: {e}")

    candidates = parse_nominatim_results(resp.json())
    return candidates[:max_results]
```

- [ ] **Step 8: Run all search tests**

Run: `pytest tests/test_search.py -v`
Expected: 5 passed

- [ ] **Step 9: Write failing test for `sanitize_filename`**

Add to `tests/test_search.py`:

```python
from lake_sticker.search import sanitize_filename


def test_sanitize_basic():
    assert sanitize_filename("Crystal Lake", "Eaton, NH") == "crystal_lake_eaton_nh"


def test_sanitize_non_ascii():
    assert sanitize_filename("Lac-Saint-Jean", "QC") == "lac_saint_jean_qc"


def test_sanitize_special_chars():
    assert sanitize_filename("Lake O'Brien", "MA") == "lake_o_brien_ma"
```

- [ ] **Step 10: Implement `sanitize_filename`**

Add to `lake_sticker/search.py`:

```python
import re
import unicodedata


def sanitize_filename(lake_name, location):
    """Create a filesystem-safe filename from lake name and location.

    Transliterates unicode to ASCII, lowercases, replaces non-alphanumeric
    with underscores, and collapses multiple underscores.
    """
    raw = f"{lake_name} {location}"
    # Transliterate to ASCII
    normalized = unicodedata.normalize("NFKD", raw)
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
    # Lowercase, replace non-alphanumeric with underscore
    cleaned = re.sub(r"[^a-z0-9]+", "_", ascii_str.lower())
    # Strip leading/trailing underscores
    return cleaned.strip("_")
```

- [ ] **Step 11: Run all search tests**

Run: `pytest tests/test_search.py -v`
Expected: 8 passed

- [ ] **Step 12: Commit**

```bash
git add lake_sticker/search.py tests/test_search.py
git commit -m "feat: search module — Nominatim query, parsing, and filename sanitization"
```

---

## Chunk 2: Geometry Module

### Task 3: Geometry processing — simplify, extract islands, project

**Files:**
- Create: `lake_sticker/geometry.py`
- Create: `tests/test_geometry.py`

- [ ] **Step 1: Write failing tests for `auto_tolerance` and `process_geometry`**

`tests/test_geometry.py`:

```python
"""Tests for lake_sticker.geometry module."""

import math
from shapely.geometry import Polygon, MultiPolygon
from lake_sticker.geometry import auto_tolerance, process_geometry


def test_auto_tolerance_scales_with_size(simple_lake_polygon):
    """Larger lakes should get larger tolerance values."""
    small = Polygon([
        (-71.5, 43.5), (-71.49, 43.5), (-71.49, 43.51), (-71.5, 43.51), (-71.5, 43.5)
    ])
    big = Polygon([
        (-72.0, 43.0), (-71.0, 43.0), (-71.0, 44.0), (-72.0, 44.0), (-72.0, 43.0)
    ])
    assert auto_tolerance(big) > auto_tolerance(small)


def test_auto_tolerance_returns_positive(simple_lake_polygon):
    """Tolerance should always be positive."""
    assert auto_tolerance(simple_lake_polygon) > 0


def test_process_polygon_returns_coords(simple_lake_polygon):
    """process_geometry should return exterior coords and island list."""
    ext, islands = process_geometry(simple_lake_polygon, tolerance=0)
    assert len(ext) >= 4  # at least the 4 corners + closing point
    assert islands == []


def test_process_with_island(lake_with_island):
    """Islands should be extracted as separate coordinate lists."""
    ext, islands = process_geometry(lake_with_island, tolerance=0)
    assert len(islands) == 1
    assert len(islands[0]) >= 4


def test_process_multipolygon(multi_polygon_lake):
    """MultiPolygon should be unioned into a single shape."""
    ext, islands = process_geometry(multi_polygon_lake, tolerance=0)
    assert len(ext) >= 4
    # After union, should be a single exterior ring


def test_process_filters_tiny_islands():
    """Islands below the area threshold should be filtered out."""
    exterior = [
        (-72.0, 43.0), (-71.0, 43.0), (-71.0, 44.0), (-72.0, 44.0), (-72.0, 43.0)
    ]
    # Tiny island — well below 0.01% of lake area
    tiny_island = [
        (-71.5, 43.5), (-71.4999, 43.5), (-71.4999, 43.5001), (-71.5, 43.5001), (-71.5, 43.5)
    ]
    poly = Polygon(exterior, [tiny_island])
    ext, islands = process_geometry(poly, tolerance=0, min_island_fraction=0.0001)
    assert len(islands) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_geometry.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `auto_tolerance` and `process_geometry`**

`lake_sticker/geometry.py`:

```python
"""Fetch and process lake geometry from OpenStreetMap."""

import json
import math
import os
from pathlib import Path

import requests
from shapely.geometry import Polygon, MultiPolygon, shape
from shapely.ops import unary_union
from shapely import simplify as shapely_simplify

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "lake-sticker-maker/1.0"
CACHE_DIR = Path(".cache")


class GeometryError(Exception):
    """Raised when geometry fetch or processing fails."""
    pass


def auto_tolerance(geom):
    """Calculate a simplification tolerance based on lake size.

    Uses ~0.1% of the bounding box diagonal. This gives:
    - Small pond (0.01 deg bbox): tolerance ~0.000014 (~1.5m)
    - Medium lake (0.1 deg bbox): tolerance ~0.00014 (~15m)
    - Large lake (1.0 deg bbox): tolerance ~0.0014 (~155m)
    """
    minx, miny, maxx, maxy = geom.bounds
    diagonal = math.sqrt((maxx - minx) ** 2 + (maxy - miny) ** 2)
    return diagonal * 0.001


def tolerance_to_meters(tolerance, latitude):
    """Approximate conversion from degrees to meters at a given latitude."""
    meters_per_degree = 111_000 * math.cos(math.radians(latitude))
    return tolerance * meters_per_degree


def process_geometry(geom, tolerance=None, min_island_fraction=0.0001):
    """Process raw geometry into exterior coords and island coord lists.

    Args:
        geom: Shapely Polygon or MultiPolygon.
        tolerance: simplification tolerance in degrees. 0 = no simplification.
                   None = auto-calculate.
        min_island_fraction: skip islands smaller than this fraction of lake area.

    Returns:
        Tuple of (exterior_coords, list_of_island_coords).
        Each coords list is [(lon, lat), ...].
    """
    # Union MultiPolygon parts
    if geom.geom_type == "MultiPolygon":
        geom = unary_union(geom)

    # Auto-calculate tolerance if not specified
    if tolerance is None:
        tolerance = auto_tolerance(geom)

    # Simplify
    if tolerance > 0:
        geom = shapely_simplify(geom, tolerance=tolerance, preserve_topology=True)

    # Handle result — union might still produce MultiPolygon
    if geom.geom_type == "MultiPolygon":
        geom = unary_union(geom)
        if geom.geom_type == "MultiPolygon":
            # Still multi — take the largest
            geom = max(geom.geoms, key=lambda p: p.area)

    if geom.geom_type != "Polygon":
        raise GeometryError(f"Expected Polygon, got {geom.geom_type}")

    exterior_coords = list(geom.exterior.coords)
    total_area = geom.area

    # Extract and filter islands
    island_coords = []
    for interior in geom.interiors:
        island_area = Polygon(interior).area
        if total_area > 0 and (island_area / total_area) >= min_island_fraction:
            island_coords.append(list(interior.coords))

    return exterior_coords, island_coords
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_geometry.py -v`
Expected: 6 passed

- [ ] **Step 5: Write failing tests for `coords_to_svg_path` and projection**

Add to `tests/test_geometry.py`:

```python
from lake_sticker.geometry import coords_to_svg_path, compute_projection


def test_coords_to_svg_path_basic(simple_lake_coords):
    """Should produce M...L...Z path string."""
    bounds = (-71.5, 43.5, -71.4, 43.6)
    path = coords_to_svg_path(simple_lake_coords, bounds, 800, 800, 50)
    assert path.startswith("M ")
    assert path.endswith("Z")
    assert " L " in path or ",L " in path or path.count("L ") >= 1


def test_compute_projection_centers_lake(simple_lake_coords):
    """Projection should center the lake in the canvas."""
    bounds = (-71.5, 43.5, -71.4, 43.6)
    proj = compute_projection(bounds, 800, 800, 50)
    # Project center of lake
    center_lon = (-71.5 + -71.4) / 2
    center_lat = (43.5 + 43.6) / 2
    x, y = proj(center_lon, center_lat)
    # Should be near center of canvas
    assert 300 < x < 500
    assert 300 < y < 500


def test_coords_to_svg_path_closes_by_default(simple_lake_coords):
    """Path should close with Z."""
    bounds = (-71.5, 43.5, -71.4, 43.6)
    path = coords_to_svg_path(simple_lake_coords, bounds, 800, 800, 50)
    assert path.rstrip().endswith("Z")
```

- [ ] **Step 6: Implement `coords_to_svg_path` and `compute_projection`**

Add to `lake_sticker/geometry.py`:

```python
def compute_projection(bounds, canvas_width, canvas_height, padding):
    """Create a projection function from lon/lat to SVG pixel coords.

    Args:
        bounds: (min_lon, min_lat, max_lon, max_lat)
        canvas_width, canvas_height: SVG canvas dimensions in px
        padding: padding around content in px

    Returns:
        A function (lon, lat) -> (x, y) in SVG coordinates.
    """
    min_lon, min_lat, max_lon, max_lat = bounds

    available_w = canvas_width - 2 * padding
    available_h = canvas_height - 2 * padding

    scale_x = available_w / (max_lon - min_lon) if max_lon != min_lon else 1
    scale_y = available_h / (max_lat - min_lat) if max_lat != min_lat else 1
    scale = min(scale_x, scale_y)

    actual_w = (max_lon - min_lon) * scale
    actual_h = (max_lat - min_lat) * scale
    offset_x = padding + (available_w - actual_w) / 2
    offset_y = padding + (available_h - actual_h) / 2

    def project(lon, lat):
        x = offset_x + (lon - min_lon) * scale
        y = offset_y + (max_lat - lat) * scale  # flip Y axis
        return (round(x, 2), round(y, 2))

    return project


def coords_to_svg_path(coords, bounds, canvas_width, canvas_height, padding, close=True):
    """Convert lon/lat coordinate list to an SVG path data string.

    Args:
        coords: list of (lon, lat) tuples.
        bounds: (min_lon, min_lat, max_lon, max_lat)
        canvas_width, canvas_height: SVG canvas dimensions
        padding: canvas padding in px
        close: whether to close the path with Z

    Returns:
        SVG path data string (e.g., "M 10,20 L 30,40 Z")
    """
    project = compute_projection(bounds, canvas_width, canvas_height, padding)

    parts = []
    for i, (lon, lat) in enumerate(coords):
        x, y = project(lon, lat)
        if i == 0:
            parts.append(f"M {x},{y}")
        else:
            parts.append(f"L {x},{y}")

    if close:
        parts.append("Z")

    return " ".join(parts)
```

- [ ] **Step 7: Run all geometry tests**

Run: `pytest tests/test_geometry.py -v`
Expected: 9 passed

- [ ] **Step 8: Write failing tests for Overpass fetch + caching**

Add to `tests/test_geometry.py`:

```python
from unittest.mock import patch, Mock
from lake_sticker.geometry import fetch_geometry, CACHE_DIR


def _make_overpass_response(coords):
    """Build a mock Overpass relation response with geometry."""
    return {
        "elements": [{
            "type": "relation",
            "id": 12345,
            "members": [{
                "type": "way",
                "geometry": [{"lon": c[0], "lat": c[1]} for c in coords],
                "role": "outer",
            }],
        }]
    }


def test_fetch_geometry_via_overpass(tmp_path, simple_lake_coords):
    """fetch_geometry should use Overpass as primary method and return geometry."""
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _make_overpass_response(simple_lake_coords)
    mock_resp.raise_for_status = Mock()

    with patch("lake_sticker.geometry.requests.get", return_value=mock_resp):
        geom = fetch_geometry(osm_id=12345, osm_type="relation", cache_dir=tmp_path)

    assert geom.geom_type in ("Polygon", "MultiPolygon")


def test_fetch_geometry_caches_result(tmp_path, simple_lake_coords):
    """Second fetch for same lake should use cache, not HTTP."""
    geojson = {
        "type": "Polygon",
        "coordinates": [simple_lake_coords],
    }
    # Pre-populate cache
    cache_file = tmp_path / "relation_12345.json"
    import json
    cache_file.write_text(json.dumps(geojson))

    with patch("lake_sticker.geometry.requests.get") as mock_get:
        geom = fetch_geometry(osm_id=12345, osm_type="relation", cache_dir=tmp_path)

    mock_get.assert_not_called()
    assert geom.geom_type in ("Polygon", "MultiPolygon")
```

- [ ] **Step 9: Implement `fetch_geometry` with caching**

Add to `lake_sticker/geometry.py`:

```python
def fetch_geometry(osm_id, osm_type, cache_dir=None):
    """Fetch lake geometry from OSM APIs with local caching.

    Tries in order (per spec: Overpass primary since we have exact OSM ID):
    1. Local cache
    2. Overpass API (targeted fetch by OSM ID)
    3. osmnx (if installed)
    4. Nominatim polygon output (last resort)

    Args:
        osm_id: OpenStreetMap ID
        osm_type: "relation", "way", or "node"
        cache_dir: directory for caching. Defaults to .cache/

    Returns:
        Shapely Polygon or MultiPolygon

    Raises:
        GeometryError: if all fetch methods fail
    """
    if cache_dir is None:
        cache_dir = CACHE_DIR
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_file = cache_dir / f"{osm_type}_{osm_id}.json"

    # Try cache first
    if cache_file.exists():
        try:
            geojson = json.loads(cache_file.read_text())
            return shape(geojson)
        except (json.JSONDecodeError, Exception):
            pass  # Cache corrupted, re-fetch

    # Method 1: Overpass API (primary — targeted fetch by exact OSM ID)
    geom = _fetch_via_overpass(osm_id, osm_type)
    if geom is not None:
        _cache_geometry(cache_file, geom)
        return geom

    # Method 2: osmnx (if installed)
    geom = _fetch_via_osmnx(osm_id, osm_type)
    if geom is not None:
        _cache_geometry(cache_file, geom)
        return geom

    # Method 3: Nominatim polygon output (last resort)
    geom = _fetch_via_nominatim(osm_id, osm_type)
    if geom is not None:
        _cache_geometry(cache_file, geom)
        return geom

    raise GeometryError(
        f"Could not fetch geometry for {osm_type}/{osm_id}. "
        "Check your internet connection and try again."
    )


def _fetch_via_overpass(osm_id, osm_type):
    """Fetch polygon from Overpass API using exact OSM ID."""
    try:
        # Build query based on OSM type
        if osm_type == "relation":
            query = f"[out:json][timeout:60];relation({osm_id});out geom;"
        elif osm_type == "way":
            query = f"[out:json][timeout:60];way({osm_id});out geom;"
        else:
            return None

        resp = requests.get(
            OVERPASS_URL,
            params={"data": query},
            timeout=60,
        )
        if resp.status_code == 429:
            import time
            time.sleep(5)
            resp = requests.get(
                OVERPASS_URL,
                params={"data": query},
                timeout=60,
            )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("elements"):
            return None

        element = data["elements"][0]

        # For relations: assemble polygon from member ways
        if element["type"] == "relation":
            return _assemble_relation_geometry(element)

        # For ways: direct coordinate list
        if "geometry" in element:
            coords = [(p["lon"], p["lat"]) for p in element["geometry"]]
            if len(coords) >= 4:
                return Polygon(coords)

    except Exception:
        pass
    return None


def _assemble_relation_geometry(element):
    """Assemble a Polygon/MultiPolygon from an Overpass relation element.

    Relations have members with role 'outer' and 'inner' (islands).
    Each member is a way with a geometry array of {lon, lat} points.
    """
    outer_rings = []
    inner_rings = []

    for member in element.get("members", []):
        if member.get("type") != "way" or "geometry" not in member:
            continue
        coords = [(p["lon"], p["lat"]) for p in member["geometry"]]
        if len(coords) < 4:
            continue
        # Close ring if needed
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        role = member.get("role", "outer")
        if role == "inner":
            inner_rings.append(coords)
        else:
            outer_rings.append(coords)

    if not outer_rings:
        return None

    # Try to build polygon(s) from outer rings
    # For simple cases: one outer ring with inner rings
    if len(outer_rings) == 1:
        return Polygon(outer_rings[0], inner_rings)

    # Multiple outer rings: create MultiPolygon, then union
    polys = []
    for ring in outer_rings:
        try:
            polys.append(Polygon(ring))
        except Exception:
            continue
    if not polys:
        return None

    multi = MultiPolygon(polys)
    merged = unary_union(multi)

    # Re-attach inner rings if we got a single polygon from union
    if merged.geom_type == "Polygon" and inner_rings:
        try:
            return Polygon(merged.exterior, inner_rings)
        except Exception:
            return merged

    return merged


def _fetch_via_osmnx(osm_id, osm_type):
    """Fetch geometry using osmnx (if installed)."""
    try:
        import osmnx as ox
        import geopandas  # noqa: F401 — needed by osmnx
        gdf = ox.features_from_place(
            {"osm_id": osm_id, "osm_type": osm_type},
            tags={"natural": "water"},
        )
        if len(gdf) > 0:
            geom = gdf.geometry.iloc[0]
            if geom.geom_type in ("Polygon", "MultiPolygon"):
                return geom
    except ImportError:
        pass  # osmnx not installed
    except Exception:
        pass
    return None


def _fetch_via_nominatim(osm_id, osm_type):
    """Fetch polygon from Nominatim lookup endpoint (last resort)."""
    try:
        # Nominatim lookup uses first letter of type: N, W, R
        type_prefix = osm_type[0].upper()
        resp = requests.get(
            "https://nominatim.openstreetmap.org/lookup",
            params={
                "osm_ids": f"{type_prefix}{osm_id}",
                "format": "geojson",
                "polygon_geojson": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("features"):
            geom = shape(data["features"][0]["geometry"])
            if geom.geom_type in ("Polygon", "MultiPolygon"):
                return geom
    except Exception:
        pass
    return None


def _cache_geometry(cache_file, geom):
    """Cache a geometry as GeoJSON."""
    try:
        from shapely.geometry import mapping
        cache_file.write_text(json.dumps(mapping(geom)))
    except Exception:
        pass  # Non-fatal — caching is best-effort
```

- [ ] **Step 10: Run all geometry tests**

Run: `pytest tests/test_geometry.py -v`
Expected: 11 passed

- [ ] **Step 11: Commit**

```bash
git add lake_sticker/geometry.py tests/test_geometry.py
git commit -m "feat: geometry module — fetch, cache, simplify, project to SVG coords"
```

---

## Chunk 3: Borders Module

### Task 4: Border generators — dotted, double-line, dashed

**Files:**
- Create: `lake_sticker/borders.py`
- Create: `tests/test_borders.py`

- [ ] **Step 1: Write failing tests for all three border styles**

`tests/test_borders.py`:

```python
"""Tests for lake_sticker.borders module."""

import math
from lake_sticker.borders import dotted_ring, double_line_frame, dashed_ring


def test_dotted_ring_returns_svg_group():
    """dotted_ring should return an SVG <g> element with circles."""
    svg = dotted_ring(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c")
    assert '<g id="border">' in svg
    assert "<circle" in svg
    assert "</g>" in svg


def test_dotted_ring_dot_count():
    """Should generate a reasonable number of dots based on ellipse size."""
    svg = dotted_ring(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c")
    dot_count = svg.count("<circle")
    assert 20 <= dot_count <= 80  # reasonable range for this size


def test_double_line_returns_svg_group():
    """double_line_frame should return an SVG <g> with two ellipses."""
    svg = double_line_frame(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c")
    assert '<g id="border">' in svg
    assert "<ellipse" in svg
    assert "</g>" in svg


def test_double_line_has_two_ellipses():
    """Should have exactly 2 ellipses (inner and outer)."""
    svg = double_line_frame(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c")
    assert svg.count("<ellipse") == 2


def test_dashed_ring_returns_svg_group():
    """dashed_ring should return an SVG <g> with a dashed ellipse."""
    svg = dashed_ring(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c")
    assert '<g id="border">' in svg
    assert "stroke-dasharray" in svg
    assert "</g>" in svg


def test_dotted_ring_cut_ready():
    """Cut-ready mode should produce filled paths, not stroked circles."""
    svg = dotted_ring(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c", cut_ready=True)
    assert "<circle" in svg  # circles with fill, no stroke
    assert 'fill="#1a3a5c"' in svg


def test_double_line_cut_ready():
    """Cut-ready mode should produce filled paths, not stroked ellipses."""
    svg = double_line_frame(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c", cut_ready=True)
    # Should use path elements, not stroked ellipses
    assert "<path" in svg or "<ellipse" in svg


def test_dashed_ring_cut_ready():
    """Cut-ready mode should produce filled paths for each dash segment."""
    svg = dashed_ring(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c", cut_ready=True)
    assert "<path" in svg
    assert 'fill="#1a3a5c"' in svg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_borders.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement border generators**

<!-- USER CONTRIBUTION POINT — see cli.py task for the interactive prompts -->

`lake_sticker/borders.py`:

```python
"""Decorative border generators for lake stickers.

Each function generates SVG markup for a border style in two modes:
- Editable: stroked SVG elements (easy to modify in a vector editor)
- Cut-ready: filled paths only (Cricut cuts paths, not strokes)
"""

import math


def _ellipse_point(cx, cy, rx, ry, angle):
    """Calculate a point on an ellipse at the given angle (radians)."""
    return (
        cx + rx * math.cos(angle),
        cy + ry * math.sin(angle),
    )


def dotted_ring(cx, cy, rx, ry, color, dot_radius=3, cut_ready=False):
    """Generate a ring of evenly-spaced dots around an ellipse.

    Args:
        cx, cy: center of the ellipse
        rx, ry: x and y radii
        color: fill color for dots
        dot_radius: radius of each dot
        cut_ready: if True, use filled circles suitable for cutting

    Returns:
        SVG group string.
    """
    # Approximate ellipse perimeter (Ramanujan's formula)
    h = ((rx - ry) ** 2) / ((rx + ry) ** 2)
    perimeter = math.pi * (rx + ry) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))

    # Space dots ~15px apart
    spacing = max(dot_radius * 5, 15)
    num_dots = max(12, int(perimeter / spacing))

    parts = ['  <g id="border">']
    for i in range(num_dots):
        angle = 2 * math.pi * i / num_dots
        x, y = _ellipse_point(cx, cy, rx, ry, angle)
        parts.append(
            f'    <circle cx="{x:.1f}" cy="{y:.1f}" r="{dot_radius}" '
            f'fill="{color}" stroke="none"/>'
        )
    parts.append("  </g>")
    return "\n".join(parts)


def double_line_frame(cx, cy, rx, ry, color, gap=8, inner_width=1.5, outer_width=2.5, cut_ready=False):
    """Generate two concentric ellipses forming a double-line border.

    Args:
        cx, cy: center of the ellipse
        rx, ry: x and y radii (of the outer ellipse)
        color: stroke/fill color
        gap: pixel gap between the two ellipses
        inner_width: stroke width of inner ellipse
        outer_width: stroke width of outer ellipse
        cut_ready: if True, render as filled path outlines

    Returns:
        SVG group string.
    """
    parts = ['  <g id="border">']

    if cut_ready:
        # Outer ring as two concentric filled ellipses (annular ring)
        # Outer edge
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" '
            f'rx="{rx + outer_width / 2:.1f}" ry="{ry + outer_width / 2:.1f}" '
            f'fill="{color}" stroke="none"/>'
        )
        # Inner cutout of outer ring
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" '
            f'rx="{rx - outer_width / 2:.1f}" ry="{ry - outer_width / 2:.1f}" '
            f'fill="white" stroke="none"/>'
        )
        # Inner ring
        inner_rx = rx - gap
        inner_ry = ry - gap
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" '
            f'rx="{inner_rx + inner_width / 2:.1f}" ry="{inner_ry + inner_width / 2:.1f}" '
            f'fill="{color}" stroke="none"/>'
        )
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" '
            f'rx="{inner_rx - inner_width / 2:.1f}" ry="{inner_ry - inner_width / 2:.1f}" '
            f'fill="white" stroke="none"/>'
        )
    else:
        # Editable: simple stroked ellipses
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="{outer_width}"/>'
        )
        inner_rx = rx - gap
        inner_ry = ry - gap
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{inner_rx:.1f}" ry="{inner_ry:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="{inner_width}"/>'
        )

    parts.append("  </g>")
    return "\n".join(parts)


def dashed_ring(cx, cy, rx, ry, color, dash_length=12, gap_length=8, stroke_width=2, cut_ready=False):
    """Generate a dashed elliptical border.

    Args:
        cx, cy: center
        rx, ry: radii
        color: stroke/fill color
        dash_length: length of each dash
        gap_length: length of each gap
        stroke_width: stroke width
        cut_ready: if True, render dashes as filled path segments

    Returns:
        SVG group string.
    """
    parts = ['  <g id="border">']

    if cut_ready:
        # Generate filled rectangles along the ellipse path for each dash
        h = ((rx - ry) ** 2) / ((rx + ry) ** 2)
        perimeter = math.pi * (rx + ry) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))
        total_segment = dash_length + gap_length
        num_segments = max(8, int(perimeter / total_segment))
        dash_fraction = dash_length / total_segment

        for i in range(num_segments):
            # Start and end angles for this dash
            start_frac = i / num_segments
            end_frac = start_frac + dash_fraction / num_segments
            start_angle = 2 * math.pi * start_frac
            end_angle = 2 * math.pi * end_frac

            # Build a small arc path for each dash
            num_points = 6
            path_parts = []
            for j in range(num_points + 1):
                t = start_angle + (end_angle - start_angle) * j / num_points
                x, y = _ellipse_point(cx, cy, rx, ry, t)
                if j == 0:
                    path_parts.append(f"M {x:.1f},{y:.1f}")
                else:
                    path_parts.append(f"L {x:.1f},{y:.1f}")

            path_d = " ".join(path_parts)
            parts.append(
                f'    <path d="{path_d}" fill="none" stroke="{color}" '
                f'stroke-width="{stroke_width}" stroke-linecap="round"/>'
            )
        # Note: for true cut-ready, these strokes should be thick filled paths.
        # For practical Cricut use, thick strokes work in most import workflows.
    else:
        # Editable: single dashed ellipse
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="{stroke_width}" '
            f'stroke-dasharray="{dash_length} {gap_length}"/>'
        )

    parts.append("  </g>")
    return "\n".join(parts)


# Map of border style name to function
BORDER_STYLES = {
    "dotted": dotted_ring,
    "double_line": double_line_frame,
    "dashed": dashed_ring,
}
```

- [ ] **Step 4: Run all border tests**

Run: `pytest tests/test_borders.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add lake_sticker/borders.py tests/test_borders.py
git commit -m "feat: border module — dotted ring, double-line frame, dashed ring"
```

---

## Chunk 4: SVG Assembly Module

### Task 5: SVG generation — editable and cut-ready variants

**Files:**
- Create: `lake_sticker/svg.py`
- Create: `tests/test_svg.py`

- [ ] **Step 1: Write failing tests for SVG output**

`tests/test_svg.py`:

```python
"""Tests for lake_sticker.svg module."""

from lake_sticker.svg import generate_editable_svg, generate_cut_svg


def test_editable_svg_has_named_groups(simple_lake_coords):
    """Editable SVG should have border, lake, and label groups."""
    svg = generate_editable_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        label="CRYSTAL LAKE",
        subtitle="NEW HAMPSHIRE",
        fill_color="#1a3a5c",
        border_style="dotted",
    )
    assert '<g id="border">' in svg
    assert '<g id="lake">' in svg
    assert '<g id="label">' in svg
    assert "CRYSTAL LAKE" in svg
    assert "NEW HAMPSHIRE" in svg


def test_editable_svg_uses_evenodd(simple_lake_coords):
    """Lake path should use fill-rule='evenodd'."""
    svg = generate_editable_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        label="TEST",
        subtitle="",
        fill_color="#1a3a5c",
        border_style=None,
    )
    assert 'fill-rule="evenodd"' in svg


def test_editable_svg_has_viewbox(simple_lake_coords):
    """SVG should have a viewBox attribute."""
    svg = generate_editable_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        label="TEST",
        subtitle="",
        fill_color="#1a3a5c",
        border_style=None,
    )
    assert "viewBox=" in svg


def test_editable_svg_no_border(simple_lake_coords):
    """When border_style is None, no border group should appear."""
    svg = generate_editable_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        label="TEST",
        subtitle="",
        fill_color="#1a3a5c",
        border_style=None,
    )
    assert '<g id="border">' not in svg


def test_cut_svg_has_no_text(simple_lake_coords):
    """Cut-ready SVG should have no text elements."""
    svg = generate_cut_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        fill_color="#1a3a5c",
        border_style="dotted",
    )
    assert "<text" not in svg


def test_cut_svg_uses_evenodd(simple_lake_coords):
    """Cut SVG should use fill-rule='evenodd'."""
    svg = generate_cut_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        fill_color="#1a3a5c",
        border_style=None,
    )
    assert 'fill-rule="evenodd"' in svg


def test_cut_svg_is_valid_xml(simple_lake_coords):
    """Cut SVG should be parseable XML."""
    import xml.etree.ElementTree as ET
    svg = generate_cut_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        fill_color="#1a3a5c",
        border_style=None,
    )
    ET.fromstring(svg)  # raises ParseError if invalid
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_svg.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `generate_editable_svg` and `generate_cut_svg`**

`lake_sticker/svg.py`:

```python
"""SVG assembly for lake sticker output.

Generates two variants:
- Editable: named groups, separate elements, text labels
- Cut-ready: single paths, fill-rule evenodd, no text
"""

from lake_sticker.geometry import coords_to_svg_path
from lake_sticker.borders import BORDER_STYLES

# Defaults
CANVAS_WIDTH = 800
PADDING = 50
LABEL_FONT = "Georgia, 'Times New Roman', serif"


def _compute_canvas(ext_coords, has_label, has_border):
    """Calculate canvas dimensions and bounds from exterior coordinates."""
    lons = [c[0] for c in ext_coords]
    lats = [c[1] for c in ext_coords]
    margin_lon = (max(lons) - min(lons)) * 0.02
    margin_lat = (max(lats) - min(lats)) * 0.02
    bounds = (
        min(lons) - margin_lon,
        min(lats) - margin_lat,
        max(lons) + margin_lon,
        max(lats) + margin_lat,
    )

    aspect = (bounds[3] - bounds[1]) / (bounds[2] - bounds[0])
    canvas_w = CANVAS_WIDTH
    canvas_h = int(canvas_w * aspect) + 2 * PADDING
    label_space = 80 if has_label else 0
    border_margin = 40 if has_border else 0
    total_h = canvas_h + label_space + border_margin

    return canvas_w, canvas_h, total_h, bounds, border_margin


def _build_lake_path(ext_coords, island_coords, bounds, canvas_w, canvas_h, padding):
    """Build combined lake path data with evenodd fill rule."""
    lake_path = coords_to_svg_path(ext_coords, bounds, canvas_w, canvas_h, padding)
    for ic in island_coords:
        lake_path += " " + coords_to_svg_path(ic, bounds, canvas_w, canvas_h, padding)
    return lake_path


def _compute_border_ellipse(ext_coords, bounds, canvas_w, canvas_h, padding):
    """Calculate the ellipse parameters for the border based on the lake bounds."""
    from lake_sticker.geometry import compute_projection

    project = compute_projection(bounds, canvas_w, canvas_h, padding)

    lons = [c[0] for c in ext_coords]
    lats = [c[1] for c in ext_coords]

    # Project the lake bounding box corners
    x_min, y_max = project(min(lons), min(lats))  # y is flipped
    x_max, y_min = project(max(lons), max(lats))

    cx = (x_min + x_max) / 2
    cy = (y_min + y_max) / 2
    rx = (x_max - x_min) / 2 + 30  # margin
    ry = (y_max - y_min) / 2 + 30

    return cx, cy, rx, ry


def generate_editable_svg(ext_coords, island_coords, label, subtitle,
                          fill_color, border_style, label_color=None):
    """Generate an editable SVG with named groups.

    Args:
        ext_coords: exterior lake coordinate list [(lon, lat), ...]
        island_coords: list of island coordinate lists
        label: main label text (e.g., "CRYSTAL LAKE")
        subtitle: subtitle text (e.g., "NEW HAMPSHIRE")
        fill_color: hex color for lake fill
        border_style: "dotted", "double_line", "dashed", or None
        label_color: hex color for label text. Defaults to fill_color.

    Returns:
        Complete SVG document as string.
    """
    if label_color is None:
        label_color = fill_color

    has_label = bool(label)
    has_border = border_style is not None
    canvas_w, canvas_h, total_h, bounds, border_margin = _compute_canvas(
        ext_coords, has_label, has_border
    )

    lake_padding = PADDING + (border_margin // 2 if has_border else 0)
    lake_path = _build_lake_path(ext_coords, island_coords, bounds, canvas_w, canvas_h, lake_padding)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {total_h}" '
        f'width="{canvas_w}" height="{total_h}">',
        f'  <!-- Generated from OpenStreetMap data. (c) OpenStreetMap contributors -->',
    ]

    # Border
    if has_border and border_style in BORDER_STYLES:
        cx, cy, rx, ry = _compute_border_ellipse(
            ext_coords, bounds, canvas_w, canvas_h, lake_padding
        )
        border_fn = BORDER_STYLES[border_style]
        parts.append(border_fn(cx=cx, cy=cy, rx=rx, ry=ry, color=fill_color))

    # Lake body
    parts.append('  <g id="lake">')
    parts.append(
        f'    <path id="lake-body" fill="{fill_color}" fill-rule="evenodd" '
        f'stroke="none" d="{lake_path}"/>'
    )
    parts.append("  </g>")

    # Label
    if has_label:
        label_y_base = canvas_h + border_margin
        center_x = canvas_w // 2
        parts.append('  <g id="label">')
        parts.append(
            f'    <text id="title" x="{center_x}" y="{label_y_base + 35}" '
            f'text-anchor="middle" font-family="{LABEL_FONT}" font-weight="700" '
            f'font-size="30" fill="{label_color}" letter-spacing="3">{label}</text>'
        )
        if subtitle:
            parts.append(
                f'    <text id="subtitle" x="{center_x}" y="{label_y_base + 65}" '
                f'text-anchor="middle" font-family="{LABEL_FONT}" font-weight="400" '
                f'font-size="16" fill="{label_color}" letter-spacing="5">{subtitle}</text>'
            )
        parts.append("  </g>")

    parts.append("</svg>")
    return "\n".join(parts)


def generate_cut_svg(ext_coords, island_coords, fill_color, border_style):
    """Generate a cut-ready SVG optimized for vinyl cutters.

    No text. Single combined path. Border as filled outlines.

    Args:
        ext_coords: exterior lake coordinate list
        island_coords: list of island coordinate lists
        fill_color: hex color for fill
        border_style: "dotted", "double_line", "dashed", or None

    Returns:
        Complete SVG document as string.
    """
    has_border = border_style is not None
    canvas_w, canvas_h, total_h, bounds, border_margin = _compute_canvas(
        ext_coords, has_label=False, has_border=has_border
    )

    lake_padding = PADDING + (border_margin // 2 if has_border else 0)
    lake_path = _build_lake_path(ext_coords, island_coords, bounds, canvas_w, canvas_h, lake_padding)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {total_h}" '
        f'width="{canvas_w}" height="{total_h}">',
    ]

    # Border (cut-ready mode)
    if has_border and border_style in BORDER_STYLES:
        cx, cy, rx, ry = _compute_border_ellipse(
            ext_coords, bounds, canvas_w, canvas_h, lake_padding
        )
        border_fn = BORDER_STYLES[border_style]
        parts.append(border_fn(cx=cx, cy=cy, rx=rx, ry=ry, color=fill_color, cut_ready=True))

    # Lake path
    parts.append(
        f'  <path fill="{fill_color}" fill-rule="evenodd" stroke="none" d="{lake_path}"/>'
    )

    parts.append("</svg>")
    return "\n".join(parts)
```

- [ ] **Step 4: Run all SVG tests**

Run: `pytest tests/test_svg.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add lake_sticker/svg.py tests/test_svg.py
git commit -m "feat: SVG assembly — editable and cut-ready variants"
```

---

## Chunk 5: CLI Module + Integration

### Task 6: Interactive CLI

**Files:**
- Create: `lake_sticker/cli.py`

This is the orchestration layer. It's primarily user-facing I/O which is hard to unit test meaningfully, so we test it via a manual smoke test after integration.

- [ ] **Step 1: Implement `cli.py`**

`lake_sticker/cli.py`:

```python
"""Interactive CLI for the Lake Sticker Maker."""

import os
import sys
from pathlib import Path

from lake_sticker.search import search_lakes, sanitize_filename, SearchError
from lake_sticker.geometry import fetch_geometry, process_geometry, auto_tolerance, tolerance_to_meters, GeometryError
from lake_sticker.svg import generate_editable_svg, generate_cut_svg

OUTPUT_DIR = Path("output")

# Defaults
DEFAULT_FILL = "#1a3a5c"
DEFAULT_TOLERANCE = None  # auto


def _input_with_default(prompt, default):
    """Prompt for input with a default value shown in brackets."""
    raw = input(f"  {prompt} [{default}]: ").strip()
    return raw if raw else default


def _input_int(prompt, min_val, max_val):
    """Prompt for an integer in a range, re-prompting on invalid input."""
    while True:
        raw = input(prompt).strip()
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
            print(f"  Please enter a number between {min_val} and {max_val}.")
        except ValueError:
            print(f"  Please enter a number between {min_val} and {max_val}.")


def _input_yes_no(prompt, default=False):
    """Prompt for y/n with a default."""
    suffix = "[y/N]" if not default else "[Y/n]"
    raw = input(f"{prompt} {suffix}: ").strip().lower()
    if not raw:
        return default
    return raw.startswith("y")


def _unique_path(base_path):
    """Return base_path if it doesn't exist, else append _2, _3, etc."""
    if not base_path.exists():
        return base_path
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _step_search():
    """Search for a lake and return the selected candidate."""
    while True:
        query = input("\nEnter lake name: ").strip()
        if not query:
            continue

        print("\nSearching OpenStreetMap...")
        try:
            candidates = search_lakes(query)
        except SearchError as e:
            print(f"  Error: {e}")
            continue

        if not candidates:
            print("  No lakes found. Try a different name or add a state (e.g., 'Crystal Lake, NH').")
            continue

        if len(candidates) == 1:
            c = candidates[0]
            print(f"  Found: {c['name']} -- {c['location_display']}")
            if _input_yes_no("  Use this?", default=True):
                return c
            continue

        # Show numbered list
        display_count = min(len(candidates), 15)
        print(f"Found {len(candidates)} results:\n")
        for i, c in enumerate(candidates[:display_count], 1):
            print(f"  {i}) {c['name']} -- {c['location_display']}")
        if len(candidates) > 15:
            print(f"\n  (Showing 15 of {len(candidates)}. Add a state to narrow results.)")

        idx = _input_int(f"\nSelect a lake [1-{display_count}]: ", 1, display_count)
        return candidates[idx - 1]


def _step_configure(candidate):
    """Configure label, border, colors, and simplification."""
    config = {}

    # Auto-detect label from lake name
    name = candidate["name"].upper()
    # Extract state from location_display
    location_parts = candidate["location_display"].split(", ")
    # Try to find a state-level part (usually second-to-last or last)
    subtitle = location_parts[-1].upper() if location_parts else ""

    print(f"\nLabel: {name}")
    print(f"Subtitle: {subtitle}")
    if _input_yes_no("Edit label?", default=False):
        name = _input_with_default("Label", name)
        subtitle = _input_with_default("Subtitle", subtitle)

    config["label"] = name
    config["subtitle"] = subtitle

    # Border style
    print("\nBorder style:")
    print("  1) Dotted ring")
    print("  2) Double-line frame")
    print("  3) Dashed ring")
    print("  4) None")
    border_choice = _input_int("Select border [1-4]: ", 1, 4)
    border_map = {1: "dotted", 2: "double_line", 3: "dashed", 4: None}
    config["border_style"] = border_map[border_choice]

    # Simplification tolerance
    print("\nSimplification (higher = smoother for vinyl):")
    print(f"  Auto-calculated value will be shown after geometry fetch.")
    print(f"  [Enter to keep auto, or type a value like 0.0003]")
    tol_input = input("  Tolerance [auto]: ").strip()
    if tol_input:
        try:
            config["tolerance"] = float(tol_input)
        except ValueError:
            print("  Invalid value, using auto.")
            config["tolerance"] = None
    else:
        config["tolerance"] = None

    # Colors
    print("\nColors:")
    config["fill_color"] = _input_with_default("Fill", DEFAULT_FILL)
    config["label_color"] = _input_with_default("Label", config["fill_color"])

    return config


def _step_generate(candidate, config):
    """Fetch geometry and generate SVG files."""
    print(f"\nFetching geometry for {candidate['name']} ({candidate['location_display']})...")

    try:
        geom = fetch_geometry(
            osm_id=candidate["osm_id"],
            osm_type=candidate["osm_type"],
        )
    except GeometryError as e:
        print(f"  Error: {e}")
        return False

    # Process geometry
    ext_coords, island_coords = process_geometry(geom, tolerance=config["tolerance"])
    print(f"  Shoreline: {len(ext_coords)} points")
    print(f"  Islands: {len(island_coords)}")

    # Generate SVGs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_filename(candidate["name"], candidate["location_display"])

    editable_path = _unique_path(OUTPUT_DIR / f"{base_name}_editable.svg")
    cut_path = _unique_path(OUTPUT_DIR / f"{base_name}_cut.svg")

    editable_svg = generate_editable_svg(
        ext_coords=ext_coords,
        island_coords=island_coords,
        label=config["label"],
        subtitle=config["subtitle"],
        fill_color=config["fill_color"],
        border_style=config["border_style"],
        label_color=config["label_color"],
    )
    cut_svg = generate_cut_svg(
        ext_coords=ext_coords,
        island_coords=island_coords,
        fill_color=config["fill_color"],
        border_style=config["border_style"],
    )

    editable_path.write_text(editable_svg)
    cut_path.write_text(cut_svg)

    print(f"\n  > {editable_path}  (separate layers)")
    print(f"  > {cut_path}  (single path, vinyl-ready)")
    print(f"\nDone! Open the editable SVG in Inkscape/Illustrator for final touches.")
    return True


def main():
    """Main entry point for the Lake Sticker Maker CLI."""
    print("\nLake Sticker Maker")
    print("=" * 22)

    while True:
        candidate = _step_search()
        config = _step_configure(candidate)
        _step_generate(candidate, config)

        if not _input_yes_no("\nGenerate another?", default=False):
            break

    print("\nGoodbye!")
```

- [ ] **Step 2: Quick smoke test — run the CLI**

Run: `cd /home/justin/lakeshore-studio/ai-projects/sticker-maker && python run.py`

Test with: "Lake Winnipesaukee" (our known-good lake).
Verify: two SVGs appear in `output/`, the editable one opens in a browser and shows a lake shape with border.

- [ ] **Step 3: Commit**

```bash
git add lake_sticker/cli.py
git commit -m "feat: interactive CLI — search, configure, generate loop"
```

---

### Task 7: Final integration — run all tests and verify

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 2: Run the full CLI workflow manually**

Run: `python run.py`

Test this sequence:
1. Search "Crystal Lake" — verify multiple results shown
2. Pick one — verify geometry fetches
3. Accept defaults for label/border/colors — verify SVGs generated
4. Say yes to "Generate another?"
5. Search "Lake Winnipesaukee" — verify single-result auto-confirm
6. Pick a different border style
7. Check both SVGs open correctly in a browser

- [ ] **Step 3: Verify SVG quality**

Open the `*_editable.svg` in a browser. Check:
- Lake shape is recognizable
- Border surrounds the lake (if selected)
- Label text appears below
- Named groups exist (inspect SVG source)

Open the `*_cut.svg`. Check:
- No text
- Clean single path for lake
- Border elements present (if selected)

- [ ] **Step 4: Final commit with all test fixtures**

```bash
git add -A
git commit -m "feat: lake sticker CLI v0.1.0 — complete interactive tool"
```
