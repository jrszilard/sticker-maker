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
