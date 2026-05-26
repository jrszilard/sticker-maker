"""Tests for lake_sticker.map.layout module."""

import math
from lake_sticker.map.layout import resolve_icon_collisions, build_legend, place_road_labels


def test_resolve_collisions_no_overlap():
    icons = [
        {"x": 100, "y": 100, "name": "A", "importance": 1},
        {"x": 300, "y": 300, "name": "B", "importance": 1},
    ]
    result = resolve_icon_collisions(icons, icon_size=40, canvas_w=800, canvas_h=600)
    assert len(result) == 2
    assert abs(result[0]["x"] - 100) < 50
    assert abs(result[1]["x"] - 300) < 50


def test_resolve_collisions_overlapping():
    icons = [
        {"x": 100, "y": 100, "name": "A", "importance": 2},
        {"x": 105, "y": 105, "name": "B", "importance": 1},
    ]
    result = resolve_icon_collisions(icons, icon_size=40, canvas_w=800, canvas_h=600)
    dx = abs(result[0]["x"] - result[1]["x"])
    dy = abs(result[0]["y"] - result[1]["y"])
    assert dx >= 30 or dy >= 30


def test_build_legend():
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
    roads = [
        {"name": "Main Street", "smoothed_coords": [(0, 0), (100, 0), (200, 0)]},
        {"name": "A Very Long Road Name That Wont Fit", "smoothed_coords": [(0, 0), (5, 0)]},
        {"name": None, "smoothed_coords": [(0, 0), (50, 0)]},
    ]
    labels = place_road_labels(roads, min_length=50)
    assert len(labels) == 1
    assert labels[0]["name"] == "Main Street"
