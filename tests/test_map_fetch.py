"""Tests for lake_sticker.map.fetch module."""

from unittest.mock import patch, Mock
from lake_sticker.map.fetch import fetch_map_data, parse_overpass_elements, build_overpass_query


def test_build_overpass_query():
    query = build_overpass_query(lat=43.58, lon=-71.21, radius=2000)
    assert "around:2000,43.58,-71.21" in query
    assert "highway" in query
    assert "natural" in query
    assert "building" in query
    assert "amenity" in query
    assert "out geom" in query


def test_parse_overpass_elements_roads():
    elements = [
        {
            "type": "way", "id": 1,
            "tags": {"highway": "primary", "name": "Main Street"},
            "geometry": [
                {"lat": 43.5, "lon": -71.5},
                {"lat": 43.51, "lon": -71.49},
                {"lat": 43.52, "lon": -71.48},
            ],
        },
    ]
    features = parse_overpass_elements(elements)
    assert len(features) == 1
    assert features[0]["type"] == "road"
    assert features[0]["name"] == "Main Street"
    assert features[0]["geometry"].geom_type == "LineString"


def test_parse_overpass_elements_pois():
    elements = [
        {
            "type": "node", "id": 2,
            "tags": {"amenity": "restaurant", "name": "Joe's Diner"},
            "lat": 43.55, "lon": -71.45,
        },
    ]
    features = parse_overpass_elements(elements)
    assert len(features) == 1
    assert features[0]["type"] == "poi"
    assert features[0]["name"] == "Joe's Diner"
    assert features[0]["geometry"].geom_type == "Point"


def test_parse_overpass_elements_water():
    elements = [
        {
            "type": "way", "id": 3,
            "tags": {"natural": "water", "name": "Crystal Lake"},
            "geometry": [
                {"lat": 43.5, "lon": -71.5}, {"lat": 43.5, "lon": -71.4},
                {"lat": 43.6, "lon": -71.4}, {"lat": 43.6, "lon": -71.5},
                {"lat": 43.5, "lon": -71.5},
            ],
        },
    ]
    features = parse_overpass_elements(elements)
    assert len(features) == 1
    assert features[0]["type"] == "water"


def test_parse_overpass_elements_buildings():
    elements = [
        {
            "type": "way", "id": 4,
            "tags": {"building": "yes"},
            "geometry": [
                {"lat": 43.55, "lon": -71.45}, {"lat": 43.55, "lon": -71.44},
                {"lat": 43.56, "lon": -71.44}, {"lat": 43.56, "lon": -71.45},
                {"lat": 43.55, "lon": -71.45},
            ],
        },
    ]
    features = parse_overpass_elements(elements)
    assert len(features) == 1
    assert features[0]["type"] == "building"


def test_parse_overpass_elements_green():
    elements = [
        {
            "type": "way", "id": 5,
            "tags": {"leisure": "park", "name": "Town Green"},
            "geometry": [
                {"lat": 43.55, "lon": -71.45}, {"lat": 43.55, "lon": -71.44},
                {"lat": 43.56, "lon": -71.44}, {"lat": 43.56, "lon": -71.45},
                {"lat": 43.55, "lon": -71.45},
            ],
        },
    ]
    features = parse_overpass_elements(elements)
    assert len(features) == 1
    assert features[0]["type"] == "green"


def test_fetch_map_data_mocked(tmp_path):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "elements": [
            {
                "type": "way", "id": 1,
                "tags": {"highway": "residential", "name": "Oak St"},
                "geometry": [
                    {"lat": 43.5, "lon": -71.5},
                    {"lat": 43.51, "lon": -71.49},
                ],
            },
        ]
    }
    mock_resp.raise_for_status = Mock()

    with patch("lake_sticker.map.fetch.requests.get", return_value=mock_resp):
        features = fetch_map_data(lat=43.58, lon=-71.21, radius=2000, cache_dir=tmp_path)

    assert len(features) == 1
    assert features[0]["type"] == "road"
