"""Tests for lake_sticker.map.icons module."""

import json
from pathlib import Path
from lake_sticker.map.icons import load_icon_mapping, resolve_icon, load_icon_svg


def test_load_icon_mapping():
    mapping = load_icon_mapping()
    assert "amenity=restaurant" in mapping
    assert mapping["amenity=restaurant"] == "restaurant"
    assert "amenity=place_of_worship" in mapping


def test_resolve_icon_exact_match():
    mapping = {"amenity=restaurant": "restaurant"}
    assert resolve_icon({"amenity": "restaurant"}, mapping) == "restaurant"


def test_resolve_icon_wildcard():
    mapping = {"shop=*": "shop"}
    assert resolve_icon({"shop": "bakery"}, mapping) == "shop"


def test_resolve_icon_specific_over_wildcard():
    mapping = {"shop=*": "shop", "shop=supermarket": "market"}
    assert resolve_icon({"shop": "supermarket"}, mapping) == "market"


def test_resolve_icon_fallback():
    mapping = {"amenity=restaurant": "restaurant"}
    assert resolve_icon({"unknown_tag": "value"}, mapping) == "pin"


def test_load_icon_svg():
    svg = load_icon_svg("pin")
    assert "<svg" in svg or "<circle" in svg or "<path" in svg
