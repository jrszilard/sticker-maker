"""Shared test fixtures for lake_sticker tests."""

import pytest
from shapely.geometry import Polygon, MultiPolygon


@pytest.fixture
def simple_lake_coords():
    """A simple square 'lake' in lon/lat coords."""
    return [
        (-71.5, 43.5),
        (-71.4, 43.5),
        (-71.4, 43.6),
        (-71.5, 43.6),
        (-71.5, 43.5),
    ]


@pytest.fixture
def simple_lake_polygon(simple_lake_coords):
    """A Shapely polygon for the simple lake."""
    return Polygon(simple_lake_coords)


@pytest.fixture
def lake_with_island():
    """A lake polygon with one island (interior ring)."""
    exterior = [
        (-71.5, 43.5),
        (-71.3, 43.5),
        (-71.3, 43.7),
        (-71.5, 43.7),
        (-71.5, 43.5),
    ]
    island = [
        (-71.45, 43.55),
        (-71.35, 43.55),
        (-71.35, 43.65),
        (-71.45, 43.65),
        (-71.45, 43.55),
    ]
    return Polygon(exterior, [island])


@pytest.fixture
def multi_polygon_lake():
    """A lake stored as MultiPolygon (two basins)."""
    p1 = Polygon([
        (-71.5, 43.5), (-71.4, 43.5), (-71.4, 43.6), (-71.5, 43.6), (-71.5, 43.5)
    ])
    p2 = Polygon([
        (-71.39, 43.5), (-71.3, 43.5), (-71.3, 43.6), (-71.39, 43.6), (-71.39, 43.5)
    ])
    return MultiPolygon([p1, p2])


@pytest.fixture
def sample_nominatim_response():
    """A realistic Nominatim search response for 'Crystal Lake'."""
    return [
        {
            "place_id": 123,
            "osm_type": "relation",
            "osm_id": 1234567,
            "display_name": "Crystal Lake, Gilmanton, Belknap County, New Hampshire, USA",
            "class": "natural",
            "type": "water",
            "boundingbox": ["43.4", "43.5", "-71.5", "-71.4"],
        },
        {
            "place_id": 456,
            "osm_type": "way",
            "osm_id": 7654321,
            "display_name": "Crystal Lake, Eaton, Carroll County, New Hampshire, USA",
            "class": "natural",
            "type": "water",
            "boundingbox": ["43.8", "43.9", "-71.1", "-71.0"],
        },
        {
            "place_id": 789,
            "osm_type": "relation",
            "osm_id": 9999999,
            "display_name": "Crystal Lake, Manchester, Hartford County, Connecticut, USA",
            "class": "place",
            "type": "locality",
            "boundingbox": ["41.7", "41.8", "-72.6", "-72.5"],
        },
    ]
