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
