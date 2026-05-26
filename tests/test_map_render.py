"""Tests for lake_sticker.map.render module."""

import xml.etree.ElementTree as ET
from shapely.geometry import LineString, Polygon, Point
from lake_sticker.map.render import generate_map_editable_svg, generate_map_cut_svg


def _sample_processed_features():
    return {
        "roads": [
            {
                "type": "road", "road_class": "primary", "name": "Main Street",
                "geometry": LineString([(-71.5, 43.5), (-71.4, 43.5), (-71.3, 43.5)]),
                "smoothed_coords": [(-71.5, 43.5), (-71.45, 43.5), (-71.4, 43.5), (-71.35, 43.5), (-71.3, 43.5)],
                "osm_tags": {"highway": "primary"},
            },
        ],
        "water": [
            {
                "type": "water", "name": "Crystal Lake",
                "geometry": Polygon([(-71.5, 43.55), (-71.4, 43.55), (-71.4, 43.65), (-71.5, 43.65), (-71.5, 43.55)]),
                "osm_tags": {"natural": "water"},
            },
        ],
        "green": [],
        "buildings": [],
        "pois": [
            {
                "type": "poi", "name": "Town Hall",
                "geometry": Point(-71.45, 43.52),
                "osm_tags": {"amenity": "townhall"},
                "icon": "house",
            },
        ],
    }


def test_editable_svg_has_all_layers():
    features = _sample_processed_features()
    svg = generate_map_editable_svg(
        features=features,
        bounds=(-71.55, 43.45, -71.25, 43.7),
        title="TEST TOWN", subtitle="NEW HAMPSHIRE",
        colors=None, border_style="dotted", label_style="none",
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
        title="WOLFEBORO", subtitle="NH",
        colors=None, border_style=None, label_style="none",
    )
    assert "WOLFEBORO" in svg


def test_editable_svg_valid_xml():
    features = _sample_processed_features()
    svg = generate_map_editable_svg(
        features=features,
        bounds=(-71.55, 43.45, -71.25, 43.7),
        title="TEST", subtitle="",
        colors=None, border_style=None, label_style="none",
    )
    ET.fromstring(svg)


def test_cut_svg_has_no_map_content():
    svg = generate_map_cut_svg(
        bounds=(-71.55, 43.45, -71.25, 43.7),
        border_style="dotted", colors=None,
    )
    assert "<text" not in svg


def test_cut_svg_valid_xml():
    svg = generate_map_cut_svg(
        bounds=(-71.55, 43.45, -71.25, 43.7),
        border_style="double_line", colors=None,
    )
    ET.fromstring(svg)
