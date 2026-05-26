"""Tests for lake_sticker.search module."""

from lake_sticker.search import parse_nominatim_results


def test_parse_filters_water_features(sample_nominatim_response):
    """Only results with water-related OSM tags should be included."""
    results = parse_nominatim_results(sample_nominatim_response)
    # Third result is class=place/type=locality — should be filtered out
    assert len(results) == 2
    assert all(r["osm_id"] != 9999999 for r in results)


def test_parse_extracts_fields(sample_nominatim_response):
    """Each result should have name, location_display, osm_id, osm_type."""
    results = parse_nominatim_results(sample_nominatim_response)
    r = results[0]
    assert r["osm_id"] == 1234567
    assert r["osm_type"] == "relation"
    assert "Crystal Lake" in r["name"]
    assert "Gilmanton" in r["location_display"]


def test_parse_handles_empty_response():
    """Empty Nominatim response should return empty list."""
    assert parse_nominatim_results([]) == []


import pytest
import requests as requests_lib
from unittest.mock import patch, Mock
from lake_sticker.search import search_lakes


def test_search_lakes_makes_nominatim_request(sample_nominatim_response):
    """search_lakes should query Nominatim and return parsed results."""
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_nominatim_response
    mock_resp.raise_for_status = Mock()

    with patch("lake_sticker.search.requests.get", return_value=mock_resp) as mock_get:
        results = search_lakes("Crystal Lake")

    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args
    assert "Crystal Lake" in str(call_kwargs)
    assert len(results) == 2  # filtered water features only


def test_search_lakes_network_error():
    """Network errors should raise SearchError, not crash."""
    with patch("lake_sticker.search.requests.get", side_effect=requests_lib.ConnectionError):
        with pytest.raises(Exception) as exc_info:
            search_lakes("Crystal Lake")
        assert "connect" in str(exc_info.value).lower() or "network" in str(exc_info.value).lower()


from lake_sticker.search import sanitize_filename


def test_sanitize_basic():
    assert sanitize_filename("Crystal Lake", "Eaton, NH") == "crystal_lake_eaton_nh"


def test_sanitize_non_ascii():
    assert sanitize_filename("Lac-Saint-Jean", "QC") == "lac_saint_jean_qc"


def test_sanitize_special_chars():
    assert sanitize_filename("Lake O'Brien", "MA") == "lake_o_brien_ma"


from lake_sticker.search import search_location, parse_location_results


def test_parse_location_results_accepts_towns():
    raw = [
        {
            "place_id": 100, "osm_type": "relation", "osm_id": 55555,
            "display_name": "Wolfeboro, Carroll County, New Hampshire, USA",
            "class": "boundary", "type": "administrative",
            "lat": "43.5803", "lon": "-71.2076",
            "boundingbox": ["43.5", "43.7", "-71.3", "-71.1"],
        },
    ]
    results = parse_location_results(raw)
    assert len(results) == 1
    r = results[0]
    assert r["name"] == "Wolfeboro"
    assert r["lat"] == 43.5803
    assert r["lon"] == -71.2076
    assert r["osm_id"] == 55555


def test_parse_location_results_captures_lat_lon():
    raw = [
        {
            "place_id": 200, "osm_type": "way", "osm_id": 66666,
            "display_name": "King's Cross, London, England, UK",
            "class": "place", "type": "suburb",
            "lat": "51.5308", "lon": "-0.1238",
            "boundingbox": ["51.52", "51.54", "-0.14", "-0.11"],
        },
    ]
    results = parse_location_results(raw)
    assert isinstance(results[0]["lat"], float)
    assert isinstance(results[0]["lon"], float)


def test_parse_location_results_empty():
    assert parse_location_results([]) == []


def test_search_location_mocked(sample_nominatim_response):
    from unittest.mock import patch, Mock
    enriched = []
    for i, item in enumerate(sample_nominatim_response):
        item_copy = dict(item)
        item_copy["lat"] = str(43.5 + i * 0.1)
        item_copy["lon"] = str(-71.5 + i * 0.1)
        enriched.append(item_copy)

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = enriched
    mock_resp.raise_for_status = Mock()

    with patch("lake_sticker.search.requests.get", return_value=mock_resp):
        results = search_location("Wolfeboro, NH")
    assert len(results) == 3  # no water filtering
