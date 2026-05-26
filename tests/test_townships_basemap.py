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


def test_render_basemap_legend_escapes_special_chars():
    # A tiny town (projected width well below MIN_LABEL_WIDTH) takes the
    # numbered-legend path; its name must still be XML-escaped there.
    tiny = {"name": "A < B", "county_fp": "011", "county": "Hillsborough",
            "geometry": _box(0, 0, 1, 1)}  # 1m wide -> below threshold at small scale
    fs = {
        "townships": [tiny],
        "counties": [{"county_fp": "011", "name": "Hillsborough",
                      "geometry": _box(0, 0, 1, 1)}],
        "state": _box(0, 0, 1, 1),
    }
    svg = render_basemap(fs, scale=1.0)
    assert 'id="legend"' in svg
    assert "A &lt; B" in svg
    ET.fromstring(svg)  # must still parse
