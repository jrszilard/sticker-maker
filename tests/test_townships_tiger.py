"""Tests for lake_sticker.townships.tiger module."""

from unittest.mock import Mock
import pytest

from lake_sticker.townships import tiger
from lake_sticker.townships.tiger import build_feature_set
from shapely.geometry import Polygon


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
