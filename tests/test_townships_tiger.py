"""Tests for lake_sticker.townships.tiger module."""

from unittest.mock import Mock
import pytest

from lake_sticker.townships import tiger


def test_nh_county_names_has_ten_counties():
    assert len(tiger.NH_COUNTY_NAMES) == 10
    assert tiger.NH_COUNTY_NAMES["011"] == "Hillsborough"
    assert tiger.NH_COUNTY_NAMES["007"] == "Coos"


def test_tiger_cousub_url():
    url = tiger.tiger_cousub_url(2024)
    assert url == (
        "https://www2.census.gov/geo/tiger/TIGER2024/COUSUB/"
        "tl_2024_33_cousub.zip"
    )


def test_resolve_tiger_year_picks_current_when_present():
    session = Mock()
    session.head.return_value = Mock(status_code=200)
    assert tiger.resolve_tiger_year(current_year=2025, session=session) == 2025
    session.head.assert_called_once()


def test_resolve_tiger_year_steps_back_when_missing():
    session = Mock()
    session.head.side_effect = [
        Mock(status_code=404),  # 2026 not published
        Mock(status_code=200),  # 2025 present
    ]
    assert tiger.resolve_tiger_year(current_year=2026, session=session) == 2025
    assert session.head.call_count == 2


def test_resolve_tiger_year_raises_after_lookback():
    session = Mock()
    session.head.return_value = Mock(status_code=404)
    with pytest.raises(RuntimeError):
        tiger.resolve_tiger_year(current_year=2026, max_lookback=2, session=session)
