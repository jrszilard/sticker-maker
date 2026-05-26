# New Hampshire Township Map & Stickers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a 24×36 in New Hampshire base-map poster SVG (state + county + township outlines and names) plus one editable, true-scale die-cut sticker SVG per county subdivision, all sharing one projection so stickers drop into their map slots like puzzle pieces.

**Architecture:** A new `lake_sticker/townships/` subpackage. geopandas is confined to reading the Census TIGER shapefile (`tiger.py`); all dissolve, reprojection (pyproj), and rendering logic operates on plain shapely geometry, mirroring the dependency-light, plain-coordinate style of the existing `lake_sticker/map/render.py`. A single shared meters→SVG scale guarantees puzzle-fit registration.

**Tech Stack:** Python ≥3.10, shapely (core dep), geopandas + pyproj (new `townships` optional extra), requests, argparse, pytest.

---

## File Structure

| File | Responsibility |
|---|---|
| `lake_sticker/townships/__init__.py` | Package marker, exported names |
| `lake_sticker/townships/tiger.py` | County FIPS map, TIGER year resolution, download/cache, shapefile read (geopandas), dissolve to feature set |
| `lake_sticker/townships/projection.py` | lat/lon→meters (pyproj), shared scale, projector factory, polygon→SVG-path helpers |
| `lake_sticker/townships/basemap.py` | Render the poster SVG (townships, counties, state, labels/legend, title) |
| `lake_sticker/townships/sticker.py` | Render one die-cut township sticker SVG |
| `lake_sticker/townships/cli.py` | `nh-map` entry point: orchestrate fetch → feature set → poster + stickers; filename sanitization |
| `tests/test_townships_tiger.py` | County map, URL, year resolution (mocked HEAD), dissolve logic, shapefile read (importorskip) |
| `tests/test_townships_projection.py` | Scale computation, puzzle-fit invariant, path building, to_meters (importorskip) |
| `tests/test_townships_basemap.py` | Poster SVG structure, dimensions, layer groups, labels |
| `tests/test_townships_sticker.py` | Sticker groups incl. empty `artwork`, viewBox fit, buffer applied |
| `tests/test_townships_cli.py` | Filename sanitization, end-to-end file output (mocked fetch) |

**Key signatures (stable across tasks):**

```python
# tiger.py
NH_STATE_FIPS = "33"
NH_COUNTY_NAMES: dict[str, str]                 # COUNTYFP (3-digit) -> county name
def tiger_cousub_url(year: int) -> str
def resolve_tiger_year(current_year=None, max_lookback=3, session=None) -> int
def download_cousub(year: int, cache_dir) -> Path     # returns path to .shp
def load_subdivisions(shapefile_path) -> list[dict]   # {name, county_fp, geometry(EPSG:4269)}
def build_feature_set(subdivisions: list[dict]) -> dict
    # {"townships": [ {name, county_fp, county, geometry} ],
    #  "counties":  [ {county_fp, name, geometry} ],
    #  "state":     geometry}

# projection.py
def to_meters(geom, dst_epsg=32110, src_epsg=4269)
def to_meters_feature_set(feature_set) -> dict        # same shape, geometries in meters
def compute_scale(bounds_m, printable_w, printable_h) -> float
def make_projector(scale, origin_x, origin_y, offset_x, offset_y, canvas_h)  # -> (x,y)->(sx,sy)
def polygon_to_path(polygon, project) -> str
def iter_polygons(geom) -> list                       # Polygon|MultiPolygon -> [Polygon,...]

# basemap.py
def render_basemap(feature_set_m, scale, poster_w=2304, poster_h=3456, margin=96) -> str

# sticker.py
def render_sticker(township_m, scale, buffer_m=60.0, margin=8) -> str

# cli.py
def sanitize_filename(name: str) -> str
def main(argv=None) -> int
```

Poster geometry: 24×36 in at 96 units/in → `poster_w=2304`, `poster_h=3456`, `margin=96` (1 in). Sticker buffer default `60.0` m (≈0.08 in white kiss-cut border at the shared scale for a poster-filling NH).

---

## Task 1: Package scaffolding and packaging

**Files:**
- Create: `lake_sticker/townships/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create the package marker**

Create `lake_sticker/townships/__init__.py`:

```python
"""New Hampshire township base map and die-cut sticker generation.

Data layer (``tiger``) uses geopandas to read US Census TIGER/Line county
subdivisions; everything downstream operates on plain shapely geometry.
"""
```

- [ ] **Step 2: Add the console script and optional extra**

In `pyproject.toml`, add a `townships` extra under `[project.optional-dependencies]` (alongside the existing `osmnx` and `dev` extras):

```toml
townships = ["geopandas>=0.14", "pyproj>=3.4"]
```

And add to `[project.scripts]` (alongside the existing `lake-sticker` script):

```toml
nh-map = "lake_sticker.townships.cli:main"
```

- [ ] **Step 3: Verify the package imports**

Run: `python -c "import lake_sticker.townships"`
Expected: no output, exit 0.

- [ ] **Step 4: Commit**

```bash
git add lake_sticker/townships/__init__.py pyproject.toml
git commit -m "feat: scaffold townships subpackage and nh-map entry point"
```

---

## Task 2: TIGER constants, URL, and year resolution

**Files:**
- Create: `lake_sticker/townships/tiger.py`
- Test: `tests/test_townships_tiger.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_townships_tiger.py`:

```python
"""Tests for lake_sticker.townships.tiger module."""

from unittest.mock import Mock
import pytest

from lake_sticker.townships import tiger


def test_nh_county_names_has_ten_counties():
    assert len(tiger.NH_COUNTY_NAMES) == 10
    assert tiger.NH_COUNTY_NAMES["011"] == "Hillsborough"
    assert tiger.NH_COUNTY_NAMES["007"] == "Coos"


def test_tiger_cousub_url():
    url = tiger.tiger_cousub_url(2024)
    assert url == (
        "https://www2.census.gov/geo/tiger/TIGER2024/COUSUB/"
        "tl_2024_33_cousub.zip"
    )


def test_resolve_tiger_year_picks_current_when_present():
    session = Mock()
    session.head.return_value = Mock(status_code=200)
    assert tiger.resolve_tiger_year(current_year=2025, session=session) == 2025
    session.head.assert_called_once()


def test_resolve_tiger_year_steps_back_when_missing():
    session = Mock()
    session.head.side_effect = [
        Mock(status_code=404),  # 2026 not published
        Mock(status_code=200),  # 2025 present
    ]
    assert tiger.resolve_tiger_year(current_year=2026, session=session) == 2025
    assert session.head.call_count == 2


def test_resolve_tiger_year_raises_after_lookback():
    session = Mock()
    session.head.return_value = Mock(status_code=404)
    with pytest.raises(RuntimeError):
        tiger.resolve_tiger_year(current_year=2026, max_lookback=2, session=session)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_townships_tiger.py -v`
Expected: FAIL — `ModuleNotFoundError` / `AttributeError` (tiger not yet implemented).

- [ ] **Step 3: Write minimal implementation**

Create `lake_sticker/townships/tiger.py`:

```python
"""US Census TIGER/Line data fetching and dissolve for NH townships."""

import datetime
import io
import logging
import zipfile
from pathlib import Path

import requests
from shapely.ops import unary_union

logger = logging.getLogger(__name__)

NH_STATE_FIPS = "33"

# NH county FIPS (3-digit COUNTYFP) -> county name.
NH_COUNTY_NAMES = {
    "001": "Belknap",
    "003": "Carroll",
    "005": "Cheshire",
    "007": "Coos",
    "009": "Grafton",
    "011": "Hillsborough",
    "013": "Merrimack",
    "015": "Rockingham",
    "017": "Strafford",
    "019": "Sullivan",
}


def tiger_cousub_url(year: int) -> str:
    """Return the Census TIGER county-subdivision zip URL for NH and *year*."""
    return (
        f"https://www2.census.gov/geo/tiger/TIGER{year}/COUSUB/"
        f"tl_{year}_{NH_STATE_FIPS}_cousub.zip"
    )


def resolve_tiger_year(current_year=None, max_lookback=3, session=None) -> int:
    """Return the newest published TIGER year, probing with HTTP HEAD.

    Starts at *current_year* and steps back up to *max_lookback* years until a
    cousub release exists. Raises RuntimeError if none is found.
    """
    if current_year is None:
        current_year = datetime.date.today().year
    sess = session or requests

    for year in range(current_year, current_year - max_lookback - 1, -1):
        url = tiger_cousub_url(year)
        try:
            resp = sess.head(url, timeout=30, allow_redirects=True)
        except requests.RequestException:
            continue
        if getattr(resp, "status_code", None) == 200:
            logger.debug("Resolved TIGER year: %s", year)
            return year

    raise RuntimeError(
        f"No published TIGER cousub release found between "
        f"{current_year - max_lookback} and {current_year}."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_townships_tiger.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add lake_sticker/townships/tiger.py tests/test_townships_tiger.py
git commit -m "feat: TIGER county map, URL builder, year resolution"
```

---

## Task 3: Download, shapefile read, and dissolve to feature set

**Files:**
- Modify: `lake_sticker/townships/tiger.py`
- Test: `tests/test_townships_tiger.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_townships_tiger.py`:

```python
from shapely.geometry import Polygon


def _box(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def test_build_feature_set_dissolves_counties_and_state():
    # Two towns in county 011, one in 007 — adjacent boxes per county.
    subs = [
        {"name": "Alpha", "county_fp": "011", "geometry": _box(0, 0, 1, 1)},
        {"name": "Beta", "county_fp": "011", "geometry": _box(1, 0, 2, 1)},
        {"name": "Gamma", "county_fp": "007", "geometry": _box(0, 1, 2, 2)},
    ]
    fs = build_feature_set(subs)

    assert len(fs["townships"]) == 3
    assert fs["townships"][0]["county"] == "Hillsborough"

    counties = {c["county_fp"]: c for c in fs["counties"]}
    assert set(counties) == {"011", "007"}
    assert counties["011"]["name"] == "Hillsborough"
    # Alpha + Beta dissolve to a single 2x1 rectangle (area 2).
    assert counties["011"]["geometry"].area == pytest.approx(2.0)

    # State is the union of everything: 2x2 square, area 4.
    assert fs["state"].area == pytest.approx(4.0)


def test_build_feature_set_unknown_county_fp_falls_back_to_code():
    subs = [{"name": "Orphan", "county_fp": "999", "geometry": _box(0, 0, 1, 1)}]
    fs = build_feature_set(subs)
    assert fs["townships"][0]["county"] == "999"
    assert fs["counties"][0]["name"] == "999"
```

Add the import at the top of the test file:

```python
from lake_sticker.townships.tiger import build_feature_set
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_townships_tiger.py -k build_feature_set -v`
Expected: FAIL — `ImportError: cannot import name 'build_feature_set'`.

- [ ] **Step 3: Write minimal implementation**

Append to `lake_sticker/townships/tiger.py`:

```python
def download_cousub(year: int, cache_dir) -> Path:
    """Download and extract the NH cousub shapefile; return the .shp path.

    Extracted into ``<cache_dir>/.cache/tiger_<year>_cousub/``. Cached: if the
    .shp already exists it is returned without a network request.
    """
    cache_dir = Path(cache_dir)
    extract_dir = cache_dir / ".cache" / f"tiger_{year}_cousub"
    shp = extract_dir / f"tl_{year}_{NH_STATE_FIPS}_cousub.shp"
    if shp.exists():
        logger.debug("Cache hit: %s", shp)
        return shp

    extract_dir.mkdir(parents=True, exist_ok=True)
    url = tiger_cousub_url(year)
    logger.debug("Downloading %s", url)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(extract_dir)
    return shp


def load_subdivisions(shapefile_path) -> list[dict]:
    """Read the cousub shapefile into plain records (geometry in EPSG:4269)."""
    import geopandas as gpd

    gdf = gpd.read_file(shapefile_path)
    if gdf.crs is not None and gdf.crs.to_epsg() != 4269:
        gdf = gdf.to_crs(epsg=4269)

    records = []
    for _, row in gdf.iterrows():
        records.append(
            {
                "name": row["NAME"],
                "county_fp": row["COUNTYFP"],
                "geometry": row["geometry"],
            }
        )
    return records


def build_feature_set(subdivisions: list[dict]) -> dict:
    """Build townships + dissolved county + state geometries.

    Returns a dict with keys ``townships``, ``counties``, ``state``.
    Geometries are passed through unchanged (caller controls the CRS).
    """
    townships = []
    by_county: dict[str, list] = {}
    for rec in subdivisions:
        fp = rec["county_fp"]
        townships.append(
            {
                "name": rec["name"],
                "county_fp": fp,
                "county": NH_COUNTY_NAMES.get(fp, fp),
                "geometry": rec["geometry"],
            }
        )
        by_county.setdefault(fp, []).append(rec["geometry"])

    counties = []
    for fp in sorted(by_county):
        counties.append(
            {
                "county_fp": fp,
                "name": NH_COUNTY_NAMES.get(fp, fp),
                "geometry": unary_union(by_county[fp]),
            }
        )

    state = unary_union([rec["geometry"] for rec in subdivisions])
    return {"townships": townships, "counties": counties, "state": state}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_townships_tiger.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Add a geopandas-guarded read smoke test**

Append to `tests/test_townships_tiger.py`:

```python
def test_load_subdivisions_reads_geodataframe(tmp_path):
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import Polygon as P

    gdf = gpd.GeoDataFrame(
        {"NAME": ["Alpha", "Beta"], "COUNTYFP": ["011", "007"]},
        geometry=[P([(0, 0), (1, 0), (1, 1), (0, 1)]),
                  P([(1, 0), (2, 0), (2, 1), (1, 1)])],
        crs="EPSG:4269",
    )
    shp = tmp_path / "sample.shp"
    gdf.to_file(shp)

    records = tiger.load_subdivisions(shp)
    assert {r["name"] for r in records} == {"Alpha", "Beta"}
    assert records[0]["geometry"].geom_type == "Polygon"
```

- [ ] **Step 6: Run the full tiger test module**

Run: `pytest tests/test_townships_tiger.py -v`
Expected: PASS, or the read test SKIPPED if geopandas is not installed.

- [ ] **Step 7: Commit**

```bash
git add lake_sticker/townships/tiger.py tests/test_townships_tiger.py
git commit -m "feat: TIGER download, shapefile read, and dissolve to feature set"
```

---

## Task 4: Projection — shared scale and puzzle-fit invariant

**Files:**
- Create: `lake_sticker/townships/projection.py`
- Test: `tests/test_townships_projection.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_townships_projection.py`:

```python
"""Tests for lake_sticker.townships.projection module."""

import pytest
from shapely.geometry import Polygon, MultiPolygon

from lake_sticker.townships import projection as proj


def _box(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def test_compute_scale_fits_smaller_dimension():
    # 1000 wide x 2000 tall meters into 100 x 100 printable -> limited by height.
    scale = proj.compute_scale((0, 0, 1000, 2000), 100, 100)
    assert scale == pytest.approx(0.05)  # 100 / 2000


def test_iter_polygons_handles_both_types():
    poly = _box(0, 0, 1, 1)
    multi = MultiPolygon([poly, _box(2, 2, 3, 3)])
    assert len(proj.iter_polygons(poly)) == 1
    assert len(proj.iter_polygons(multi)) == 2


def test_puzzle_fit_same_scale_yields_same_rendered_size():
    # A town box in meters. Project it as part of the basemap and as a sticker;
    # the rendered width/height must be identical because scale is shared.
    scale = 0.05
    town = _box(500, 500, 700, 900)  # 200m x 400m

    basemap_project = proj.make_projector(
        scale, origin_x=0, origin_y=0, offset_x=10, offset_y=10, canvas_h=200
    )
    sticker_project = proj.make_projector(
        scale, origin_x=500, origin_y=500, offset_x=8, offset_y=8, canvas_h=216
    )

    def bbox(project):
        pts = [project(x, y) for x, y in town.exterior.coords]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (max(xs) - min(xs), max(ys) - min(ys))

    bw, bh = bbox(basemap_project)
    sw, sh = bbox(sticker_project)
    assert bw == pytest.approx(sw)
    assert bh == pytest.approx(sh)
    assert bw == pytest.approx(200 * scale)
    assert bh == pytest.approx(400 * scale)


def test_polygon_to_path_emits_move_line_close():
    project = proj.make_projector(1.0, 0, 0, 0, 0, 10)
    d = proj.polygon_to_path(_box(0, 0, 2, 2), project)
    assert d.startswith("M ")
    assert " L " in d
    assert d.rstrip().endswith("Z")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_townships_projection.py -v`
Expected: FAIL — module/functions not defined.

- [ ] **Step 3: Write minimal implementation**

Create `lake_sticker/townships/projection.py`:

```python
"""Reprojection and the single shared meters->SVG transform.

The shared ``scale`` (SVG units per metre) is what guarantees puzzle-fit: the
base map and every sticker apply the *same* scale, differing only in translate.
"""

from shapely.ops import transform as shapely_transform


def to_meters(geom, dst_epsg=32110, src_epsg=4269):
    """Reproject a shapely geometry from lat/lon to a metre-based CRS.

    Default destination is NH State Plane (EPSG:32110, metres).
    """
    from pyproj import Transformer

    transformer = Transformer.from_crs(
        f"EPSG:{src_epsg}", f"EPSG:{dst_epsg}", always_xy=True
    )
    return shapely_transform(transformer.transform, geom)


def to_meters_feature_set(feature_set, dst_epsg=32110, src_epsg=4269) -> dict:
    """Return a copy of *feature_set* with all geometries reprojected to metres."""
    townships = [
        {**t, "geometry": to_meters(t["geometry"], dst_epsg, src_epsg)}
        for t in feature_set["townships"]
    ]
    counties = [
        {**c, "geometry": to_meters(c["geometry"], dst_epsg, src_epsg)}
        for c in feature_set["counties"]
    ]
    state = to_meters(feature_set["state"], dst_epsg, src_epsg)
    return {"townships": townships, "counties": counties, "state": state}


def compute_scale(bounds_m, printable_w, printable_h) -> float:
    """SVG units per metre so the bounds fit within printable_w x printable_h."""
    minx, miny, maxx, maxy = bounds_m
    span_x = (maxx - minx) or 1.0
    span_y = (maxy - miny) or 1.0
    return min(printable_w / span_x, printable_h / span_y)


def make_projector(scale, origin_x, origin_y, offset_x, offset_y, canvas_h):
    """Return a function mapping metre coords to SVG coords (y flipped down)."""

    def project(x, y):
        sx = offset_x + (x - origin_x) * scale
        sy = canvas_h - (offset_y + (y - origin_y) * scale)
        return (round(sx, 2), round(sy, 2))

    return project


def iter_polygons(geom):
    """Yield Polygon parts of a Polygon or MultiPolygon (empty for others)."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    return []


def _ring_to_path(coords) -> str:
    parts = []
    for i, (x, y) in enumerate(coords):
        parts.append(f"{'M' if i == 0 else 'L'} {x},{y}")
    parts.append("Z")
    return " ".join(parts)


def polygon_to_path(polygon, project) -> str:
    """Build an SVG path (with holes) from a shapely Polygon and a projector."""
    d = _ring_to_path([project(x, y) for x, y in polygon.exterior.coords])
    for interior in polygon.interiors:
        d += " " + _ring_to_path([project(x, y) for x, y in interior.coords])
    return d
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_townships_projection.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Add a pyproj-guarded reprojection test**

Append to `tests/test_townships_projection.py`:

```python
def test_to_meters_changes_coordinate_magnitude():
    pytest.importorskip("pyproj")
    # A small box near Concord, NH in lat/lon -> metres (State Plane).
    geom = _box(-71.55, 43.18, -71.50, 43.22)
    projected = proj.to_meters(geom)
    minx, miny, maxx, maxy = projected.bounds
    # State Plane NH coordinates are large positive metre values.
    assert maxx - minx > 1000
    assert maxy - miny > 1000
```

- [ ] **Step 6: Run the full projection test module**

Run: `pytest tests/test_townships_projection.py -v`
Expected: PASS, or the reprojection test SKIPPED if pyproj is not installed.

- [ ] **Step 7: Commit**

```bash
git add lake_sticker/townships/projection.py tests/test_townships_projection.py
git commit -m "feat: shared meters->SVG projection with puzzle-fit invariant"
```

---

## Task 5: Base-map renderer

**Files:**
- Create: `lake_sticker/townships/basemap.py`
- Test: `tests/test_townships_basemap.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_townships_basemap.py`:

```python
"""Tests for lake_sticker.townships.basemap module."""

import xml.etree.ElementTree as ET

import pytest
from shapely.geometry import Polygon

from lake_sticker.townships.basemap import render_basemap


def _box(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def _feature_set_m():
    # Two towns (metres), already "projected": a 2000 x 1000 m state.
    t1 = {"name": "Alpha", "county_fp": "011", "county": "Hillsborough",
          "geometry": _box(0, 0, 1000, 1000)}
    t2 = {"name": "Beta", "county_fp": "011", "county": "Hillsborough",
          "geometry": _box(1000, 0, 2000, 1000)}
    county = {"county_fp": "011", "name": "Hillsborough",
              "geometry": _box(0, 0, 2000, 1000)}
    state = _box(0, 0, 2000, 1000)
    return {"townships": [t1, t2], "counties": [county], "state": state}


def test_render_basemap_dimensions_and_root():
    svg = render_basemap(_feature_set_m(), scale=1.0, poster_w=2304,
                         poster_h=3456, margin=96)
    root = ET.fromstring(svg)
    assert root.attrib["viewBox"] == "0 0 2304 3456"
    assert root.attrib["width"] == "24in"
    assert root.attrib["height"] == "36in"


def test_render_basemap_has_expected_layers():
    svg = render_basemap(_feature_set_m(), scale=1.0)
    for layer_id in ("townships", "counties", "state", "labels", "title"):
        assert f'id="{layer_id}"' in svg


def test_render_basemap_includes_town_names_and_title():
    svg = render_basemap(_feature_set_m(), scale=1.0)
    assert "Alpha" in svg
    assert "Beta" in svg
    assert "NEW HAMPSHIRE" in svg


def test_render_basemap_escapes_ampersand_in_name():
    fs = _feature_set_m()
    fs["townships"][0]["name"] = "A & B"
    svg = render_basemap(fs, scale=1.0)
    assert "A &amp; B" in svg
    # Resulting SVG must still parse.
    ET.fromstring(svg)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_townships_basemap.py -v`
Expected: FAIL — module not defined.

- [ ] **Step 3: Write minimal implementation**

Create `lake_sticker/townships/basemap.py`:

```python
"""Render the New Hampshire base-map poster SVG."""

from xml.sax.saxutils import escape

from lake_sticker.townships.projection import (
    iter_polygons,
    make_projector,
    polygon_to_path,
)

SERIF = "Georgia, 'Times New Roman', serif"
INK = "#3d405b"

# A town whose projected width is below this (SVG units) gets a numbered marker
# and a legend entry instead of an inline name label.
MIN_LABEL_WIDTH = 36.0


def _font_size_for_width(width_units: float) -> float:
    """Pick a label font size from the polygon's projected width."""
    return max(7.0, min(14.0, width_units / 10.0))


def render_basemap(feature_set_m, scale, poster_w=2304, poster_h=3456, margin=96) -> str:
    """Render the poster from a metres-based feature set and shared *scale*.

    Geometries in *feature_set_m* must already be in metres (see
    ``projection.to_meters_feature_set``). The same *scale* is reused for the
    stickers so they register against the map.
    """
    state = feature_set_m["state"]
    minx, miny, maxx, maxy = state.bounds
    printable_w = poster_w - 2 * margin
    printable_h = poster_h - 2 * margin
    used_w = (maxx - minx) * scale
    used_h = (maxy - miny) * scale
    offset_x = margin + (printable_w - used_w) / 2
    offset_y = margin + (printable_h - used_h) / 2
    project = make_projector(scale, minx, miny, offset_x, offset_y, poster_h)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {poster_w} {poster_h}" width="24in" height="36in">',
        "  <!-- Source: U.S. Census Bureau TIGER/Line -->",
    ]

    # Townships (thin outlines, no fill).
    parts.append(f'  <g id="townships" fill="none" stroke="{INK}" stroke-width="1">')
    for t in feature_set_m["townships"]:
        for poly in iter_polygons(t["geometry"]):
            parts.append(f'    <path d="{polygon_to_path(poly, project)}"/>')
    parts.append("  </g>")

    # Counties (medium outlines).
    parts.append(f'  <g id="counties" fill="none" stroke="{INK}" stroke-width="3">')
    for c in feature_set_m["counties"]:
        for poly in iter_polygons(c["geometry"]):
            parts.append(f'    <path d="{polygon_to_path(poly, project)}"/>')
    parts.append("  </g>")

    # State (thick outline).
    parts.append(f'  <g id="state" fill="none" stroke="{INK}" stroke-width="6">')
    for poly in iter_polygons(state):
        parts.append(f'    <path d="{polygon_to_path(poly, project)}"/>')
    parts.append("  </g>")

    # Labels: inline name when the town is big enough, else a numbered marker.
    legend = []
    parts.append(
        f'  <g id="labels" fill="{INK}" font-family="{SERIF}" text-anchor="middle">'
    )
    for t in feature_set_m["townships"]:
        geom = t["geometry"]
        gminx, gminy, gmaxx, gmaxy = geom.bounds
        width_units = (gmaxx - gminx) * scale
        pt = geom.representative_point()
        x, y = project(pt.x, pt.y)
        if width_units >= MIN_LABEL_WIDTH:
            fs = _font_size_for_width(width_units)
            parts.append(
                f'    <text x="{x}" y="{y}" font-size="{fs:.1f}">'
                f"{escape(t['name'])}</text>"
            )
        else:
            number = len(legend) + 1
            legend.append((number, t["name"]))
            parts.append(
                f'    <text x="{x}" y="{y}" font-size="7">{number}</text>'
            )
    parts.append("  </g>")

    # Legend block for numbered (too-small) towns, lower-left margin.
    if legend:
        parts.append(
            f'  <g id="legend" fill="{INK}" font-family="{SERIF}" font-size="10">'
        )
        lx = margin
        ly = poster_h - margin - len(legend) * 14
        for number, name in legend:
            parts.append(
                f'    <text x="{lx}" y="{ly}">{number}. {escape(name)}</text>'
            )
            ly += 14
        parts.append("  </g>")

    # Title.
    parts.append('  <g id="title">')
    parts.append(
        f'    <text x="{poster_w / 2}" y="{margin}" text-anchor="middle" '
        f'font-family="{SERIF}" font-size="64" font-weight="700" '
        f'fill="{INK}" letter-spacing="6">NEW HAMPSHIRE</text>'
    )
    parts.append("  </g>")

    parts.append("</svg>")
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_townships_basemap.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add lake_sticker/townships/basemap.py tests/test_townships_basemap.py
git commit -m "feat: NH base-map poster renderer with labels and legend"
```

---

## Task 6: Sticker renderer

**Files:**
- Create: `lake_sticker/townships/sticker.py`
- Test: `tests/test_townships_sticker.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_townships_sticker.py`:

```python
"""Tests for lake_sticker.townships.sticker module."""

import xml.etree.ElementTree as ET

import pytest
from shapely.geometry import Polygon

from lake_sticker.townships.sticker import render_sticker


def _box(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def _township_m():
    return {"name": "Alpha", "county_fp": "011", "county": "Hillsborough",
            "geometry": _box(1000, 2000, 1500, 2400)}  # 500 x 400 m


def test_render_sticker_has_required_groups():
    svg = render_sticker(_township_m(), scale=0.1, buffer_m=50, margin=8)
    for group_id in ("cut", "boundary", "label", "artwork"):
        assert f'id="{group_id}"' in svg


def test_render_sticker_artwork_group_is_empty():
    svg = render_sticker(_township_m(), scale=0.1)
    root = ET.fromstring(svg)
    ns = {"s": "http://www.w3.org/2000/svg"}
    artwork = root.find(".//s:g[@id='artwork']", ns)
    assert artwork is not None
    # No drawable children — just a placeholder comment.
    assert len(list(artwork)) == 0


def test_render_sticker_viewbox_fits_buffered_shape():
    scale = 0.1
    buffer_m = 50
    margin = 8
    svg = render_sticker(_township_m(), scale=scale, buffer_m=buffer_m, margin=margin)
    root = ET.fromstring(svg)
    _, _, vb_w, vb_h = [float(v) for v in root.attrib["viewBox"].split()]
    # Shape 500x400 m + 2*buffer, times scale, + 2*margin units.
    expected_w = (500 + 2 * buffer_m) * scale + 2 * margin
    expected_h = (400 + 2 * buffer_m) * scale + 2 * margin
    assert vb_w == pytest.approx(expected_w, abs=1.0)
    assert vb_h == pytest.approx(expected_h, abs=1.0)


def test_render_sticker_includes_name():
    svg = render_sticker(_township_m(), scale=0.1)
    assert "Alpha" in svg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_townships_sticker.py -v`
Expected: FAIL — module not defined.

- [ ] **Step 3: Write minimal implementation**

Create `lake_sticker/townships/sticker.py`:

```python
"""Render a single true-scale die-cut township sticker SVG."""

from xml.sax.saxutils import escape

from lake_sticker.townships.projection import (
    iter_polygons,
    make_projector,
    polygon_to_path,
)

SERIF = "Georgia, 'Times New Roman', serif"
INK = "#3d405b"
CUT = "#ff00ff"  # conventional magenta cut-line colour


def render_sticker(township_m, scale, buffer_m=60.0, margin=8) -> str:
    """Render one township sticker at the shared *scale*.

    *township_m* geometry must be in metres. The cut path is the boundary
    expanded by *buffer_m* metres (the kiss-cut white border); *margin* is
    extra SVG units of padding around the cut inside the viewBox.
    """
    geom = township_m["geometry"]
    cut_geom = geom.buffer(buffer_m)

    minx, miny, maxx, maxy = cut_geom.bounds
    canvas_w = (maxx - minx) * scale + 2 * margin
    canvas_h = (maxy - miny) * scale + 2 * margin
    project = make_projector(scale, minx, miny, margin, margin, canvas_h)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {canvas_w:.2f} {canvas_h:.2f}" '
        f'width="{canvas_w:.2f}" height="{canvas_h:.2f}">',
        f"  <!-- {escape(township_m['name'])}, "
        f"{escape(township_m['county'])} County, NH. "
        f"Source: U.S. Census Bureau TIGER/Line -->",
    ]

    # Cut path (die-cut outline, buffered).
    parts.append(f'  <g id="cut" fill="none" stroke="{CUT}" stroke-width="1">')
    for poly in iter_polygons(cut_geom):
        parts.append(f'    <path d="{polygon_to_path(poly, project)}"/>')
    parts.append("  </g>")

    # Boundary (the real town outline, just inside the cut).
    parts.append(f'  <g id="boundary" fill="none" stroke="{INK}" stroke-width="1.5">')
    for poly in iter_polygons(geom):
        parts.append(f'    <path d="{polygon_to_path(poly, project)}"/>')
    parts.append("  </g>")

    # Name label at the shape's representative point.
    pt = geom.representative_point()
    lx, ly = project(pt.x, pt.y)
    parts.append(f'  <g id="label">')
    parts.append(
        f'    <text x="{lx}" y="{ly}" text-anchor="middle" '
        f'font-family="{SERIF}" font-size="10" font-weight="700" '
        f'fill="{INK}">{escape(township_m["name"])}</text>'
    )
    parts.append("  </g>")

    # Empty artwork group, centred on the shape — drop unique art here.
    parts.append(
        f'  <g id="artwork" transform="translate({lx},{ly})">'
    )
    parts.append("    <!-- Add unique per-town artwork here -->")
    parts.append("  </g>")

    parts.append("</svg>")
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_townships_sticker.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add lake_sticker/townships/sticker.py tests/test_townships_sticker.py
git commit -m "feat: die-cut township sticker renderer with empty artwork group"
```

---

## Task 7: CLI orchestration and filename sanitization

**Files:**
- Create: `lake_sticker/townships/cli.py`
- Test: `tests/test_townships_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_townships_cli.py`:

```python
"""Tests for lake_sticker.townships.cli module."""

from unittest.mock import patch

from shapely.geometry import Polygon

from lake_sticker.townships import cli


def _box(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def test_sanitize_filename():
    assert cli.sanitize_filename("Hart's Location") == "harts_location"
    assert cli.sanitize_filename("Lincoln") == "lincoln"
    assert cli.sanitize_filename("Coös Junction") == "coos_junction"


def test_main_writes_basemap_and_stickers(tmp_path):
    # A metres-based feature set returned in place of the network/geopandas path.
    fs_m = {
        "townships": [
            {"name": "Alpha", "county_fp": "011", "county": "Hillsborough",
             "geometry": _box(0, 0, 1000, 1000)},
            {"name": "Beta", "county_fp": "007", "county": "Coos",
             "geometry": _box(1000, 0, 2000, 1000)},
        ],
        "counties": [
            {"county_fp": "011", "name": "Hillsborough", "geometry": _box(0, 0, 1000, 1000)},
            {"county_fp": "007", "name": "Coos", "geometry": _box(1000, 0, 2000, 1000)},
        ],
        "state": _box(0, 0, 2000, 1000),
    }

    with patch.object(cli, "_load_feature_set_m", return_value=fs_m):
        rc = cli.main(["--out-dir", str(tmp_path)])

    assert rc == 0
    assert (tmp_path / "nh_basemap.svg").exists()
    assert (tmp_path / "stickers" / "Hillsborough" / "alpha.svg").exists()
    assert (tmp_path / "stickers" / "Coos" / "beta.svg").exists()


def test_main_basemap_only_skips_stickers(tmp_path):
    fs_m = {
        "townships": [
            {"name": "Alpha", "county_fp": "011", "county": "Hillsborough",
             "geometry": _box(0, 0, 1000, 1000)},
        ],
        "counties": [
            {"county_fp": "011", "name": "Hillsborough", "geometry": _box(0, 0, 1000, 1000)},
        ],
        "state": _box(0, 0, 1000, 1000),
    }
    with patch.object(cli, "_load_feature_set_m", return_value=fs_m):
        rc = cli.main(["--out-dir", str(tmp_path), "--basemap-only"])
    assert rc == 0
    assert (tmp_path / "nh_basemap.svg").exists()
    assert not (tmp_path / "stickers").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_townships_cli.py -v`
Expected: FAIL — module not defined.

- [ ] **Step 3: Write minimal implementation**

Create `lake_sticker/townships/cli.py`:

```python
"""`nh-map` command: build the NH base map and per-township stickers."""

import argparse
import logging
import re
import unicodedata
from pathlib import Path

from lake_sticker.townships.basemap import render_basemap
from lake_sticker.townships.projection import compute_scale, to_meters_feature_set
from lake_sticker.townships.sticker import render_sticker
from lake_sticker.townships.tiger import (
    build_feature_set,
    download_cousub,
    load_subdivisions,
    resolve_tiger_year,
)

logger = logging.getLogger(__name__)

POSTER_W = 2304   # 24 in * 96
POSTER_H = 3456   # 36 in * 96
MARGIN = 96       # 1 in


def sanitize_filename(name: str) -> str:
    """Lowercase ASCII slug: strip accents/punctuation, spaces -> underscores."""
    ascii_name = (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    ascii_name = ascii_name.lower()
    ascii_name = re.sub(r"[^a-z0-9]+", "_", ascii_name)
    return ascii_name.strip("_")


def _load_feature_set_m(year, cache_dir):
    """Resolve year, download, read, dissolve, and reproject to metres.

    Isolated so tests can patch it without touching the network or geopandas.
    """
    resolved = year or resolve_tiger_year()
    shp = download_cousub(resolved, cache_dir)
    subdivisions = load_subdivisions(shp)
    feature_set = build_feature_set(subdivisions)
    return to_meters_feature_set(feature_set)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="nh-map",
        description="Generate a New Hampshire base map and township stickers.",
    )
    parser.add_argument("--out-dir", default="output", help="Output directory.")
    parser.add_argument("--cache-dir", default=".", help="Base dir for .cache/.")
    parser.add_argument("--year", type=int, default=None,
                        help="Force a TIGER vintage year (skips auto-resolve).")
    parser.add_argument("--basemap-only", action="store_true",
                        help="Render only the base map poster.")
    parser.add_argument("--no-stickers", action="store_true",
                        help="Alias for --basemap-only.")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fs_m = _load_feature_set_m(args.year, args.cache_dir)
    scale = compute_scale(
        fs_m["state"].bounds, POSTER_W - 2 * MARGIN, POSTER_H - 2 * MARGIN
    )

    basemap_svg = render_basemap(fs_m, scale, POSTER_W, POSTER_H, MARGIN)
    (out_dir / "nh_basemap.svg").write_text(basemap_svg, encoding="utf-8")
    logger.info("Wrote base map (%d townships)", len(fs_m["townships"]))

    if args.basemap_only or args.no_stickers:
        return 0

    stickers_dir = out_dir / "stickers"
    for township in fs_m["townships"]:
        county_dir = stickers_dir / township["county"]
        county_dir.mkdir(parents=True, exist_ok=True)
        svg = render_sticker(township, scale)
        fname = sanitize_filename(township["name"]) + ".svg"
        (county_dir / fname).write_text(svg, encoding="utf-8")

    logger.info("Wrote %d township stickers", len(fs_m["townships"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_townships_cli.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full test suite**

Run: `pytest -q`
Expected: PASS — all existing tests plus the new township tests (pyproj/geopandas-guarded tests may SKIP if those extras are not installed).

- [ ] **Step 6: Commit**

```bash
git add lake_sticker/townships/cli.py tests/test_townships_cli.py
git commit -m "feat: nh-map CLI to emit base map and per-township stickers"
```

---

## Task 8: End-to-end smoke run and docs

**Files:**
- Modify: `lake_sticker/townships/__init__.py` (optional exports)
- Modify: `CLAUDE.md` (commands section)

- [ ] **Step 1: Install the townships extra**

Run: `pip install -e ".[townships]"`
Expected: geopandas and pyproj install successfully.

- [ ] **Step 2: Real end-to-end run (network)**

Run: `nh-map --out-dir output/nh`
Expected: downloads the latest TIGER cousub once, writes `output/nh/nh_basemap.svg` and `output/nh/stickers/<County>/<town>.svg` for every NH subdivision (~259 files). Confirm the basemap opens in a browser and the state/county/township outlines and names render.

- [ ] **Step 3: Spot-check puzzle fit**

Open `output/nh/nh_basemap.svg` and one sticker (e.g. `output/nh/stickers/Hillsborough/manchester.svg`). Confirm the sticker's town outline matches the corresponding slot's size on the poster (same scale).

- [ ] **Step 4: Document the command**

In `CLAUDE.md` under `## Commands`, add:

````markdown
```bash
# Generate the New Hampshire base map + township stickers
nh-map --out-dir output/nh
```
````

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document nh-map command"
```

---

## Self-Review Notes

- **Spec coverage:** Data source/year resolution (Tasks 2–3), all ~259 subdivisions incl. unincorporated (no incorporated-only filter — Task 3 keeps every record), TIGER dissolve to county/state (Task 3), NH State Plane reprojection + shared scale (Task 4), puzzle-fit invariant (Task 4 test), 24×36 poster with thin/medium/thick tiers + names + numbered-legend fallback (Task 5), die-cut sticker with cut/boundary/label/empty-artwork groups + kiss-cut buffer + tight viewBox (Task 6), one-file-per-township into per-county folders with sanitized names + `--year`/`--basemap-only` flags (Task 7), geopandas isolated to `tiger.load_subdivisions` (Task 3).
- **Offline tests:** All logic tests run on plain shapely fixtures; geopandas/pyproj paths use `pytest.importorskip` so the suite passes without the extra installed.
- **Default EPSG:** 32110 (NH State Plane, metres). If unavailable in a given pyproj build, switch the `dst_epsg` default to 32619 (UTM 19N); the scale derivation is identical either way.
