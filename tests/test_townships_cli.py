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
