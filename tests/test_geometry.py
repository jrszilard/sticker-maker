"""Tests for lake_sticker.geometry module."""

import json
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
    assert len(ext) >= 4
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


def test_process_filters_tiny_islands():
    """Islands below the area threshold should be filtered out."""
    exterior = [
        (-72.0, 43.0), (-71.0, 43.0), (-71.0, 44.0), (-72.0, 44.0), (-72.0, 43.0)
    ]
    tiny_island = [
        (-71.5, 43.5), (-71.4999, 43.5), (-71.4999, 43.5001), (-71.5, 43.5001), (-71.5, 43.5)
    ]
    poly = Polygon(exterior, [tiny_island])
    ext, islands = process_geometry(poly, tolerance=0, min_island_fraction=0.0001)
    assert len(islands) == 0


# Part B tests
from lake_sticker.geometry import coords_to_svg_path, compute_projection


def test_coords_to_svg_path_basic(simple_lake_coords):
    """Should produce M...L...Z path string."""
    bounds = (-71.5, 43.5, -71.4, 43.6)
    path = coords_to_svg_path(simple_lake_coords, bounds, 800, 800, 50)
    assert path.startswith("M ")
    assert path.endswith("Z")
    assert path.count("L ") >= 1


def test_compute_projection_centers_lake(simple_lake_coords):
    """Projection should center the lake in the canvas."""
    bounds = (-71.5, 43.5, -71.4, 43.6)
    proj = compute_projection(bounds, 800, 800, 50)
    center_lon = (-71.5 + -71.4) / 2
    center_lat = (43.5 + 43.6) / 2
    x, y = proj(center_lon, center_lat)
    assert 300 < x < 500
    assert 300 < y < 500


def test_coords_to_svg_path_closes_by_default(simple_lake_coords):
    """Path should close with Z."""
    bounds = (-71.5, 43.5, -71.4, 43.6)
    path = coords_to_svg_path(simple_lake_coords, bounds, 800, 800, 50)
    assert path.rstrip().endswith("Z")


# Part C tests
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
    cache_file = tmp_path / "relation_12345.json"
    cache_file.write_text(json.dumps(geojson))

    with patch("lake_sticker.geometry.requests.get") as mock_get:
        geom = fetch_geometry(osm_id=12345, osm_type="relation", cache_dir=tmp_path)

    mock_get.assert_not_called()
    assert geom.geom_type in ("Polygon", "MultiPolygon")
