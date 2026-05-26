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
    coords = [(0, 0), (1, 0), (1, 1), (0, 1)]
    smoothed = chaikin_smooth(coords, iterations=2)
    assert len(smoothed) > len(coords)


def test_chaikin_smooth_preserves_approximate_shape():
    coords = [(0, 0), (10, 0), (10, 10)]
    smoothed = chaikin_smooth(coords, iterations=2)
    # Chaikin cuts corners: first point moves toward midline, last x stays near 10
    assert abs(smoothed[0][0]) < 5
    assert abs(smoothed[-1][0] - 10) < 3


def test_classify_road_primary():
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
    assert classify_road({"highway": "service"}) is None
    assert classify_road({"highway": "construction"}) is None


def test_filter_roads():
    features = [
        {"type": "road", "osm_tags": {"highway": "primary"}, "geometry": LineString([(0, 0), (1, 1)]), "name": "Main", "subtype": ""},
        {"type": "road", "osm_tags": {"highway": "service"}, "geometry": LineString([(0, 0), (1, 1)]), "name": None, "subtype": ""},
    ]
    filtered = filter_roads(features)
    assert len(filtered) == 1
    assert filtered[0]["name"] == "Main"


def test_simplify_buildings():
    small = Polygon([(0, 0), (0.00001, 0), (0.00001, 0.00001), (0, 0.00001), (0, 0)])
    big = Polygon([(0, 0), (0.001, 0), (0.001, 0.001), (0, 0.001), (0, 0)])
    features = [
        {"type": "building", "geometry": small, "name": None, "subtype": "", "osm_tags": {}},
        {"type": "building", "geometry": big, "name": None, "subtype": "", "osm_tags": {}},
    ]
    result = simplify_buildings(features, min_area=0.0000001)
    assert len(result) == 1


def test_process_map_features_returns_categorized():
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
