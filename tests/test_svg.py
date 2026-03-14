"""Tests for lake_sticker.svg module."""

from lake_sticker.svg import generate_editable_svg, generate_cut_svg


def test_editable_svg_has_named_groups(simple_lake_coords):
    """Editable SVG should have border, lake, and label groups."""
    svg = generate_editable_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        label="CRYSTAL LAKE",
        subtitle="NEW HAMPSHIRE",
        fill_color="#1a3a5c",
        border_style="dotted",
    )
    assert '<g id="border">' in svg
    assert '<g id="lake">' in svg
    assert '<g id="label">' in svg
    assert "CRYSTAL LAKE" in svg
    assert "NEW HAMPSHIRE" in svg


def test_editable_svg_uses_evenodd(simple_lake_coords):
    """Lake path should use fill-rule='evenodd'."""
    svg = generate_editable_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        label="TEST",
        subtitle="",
        fill_color="#1a3a5c",
        border_style=None,
    )
    assert 'fill-rule="evenodd"' in svg


def test_editable_svg_has_viewbox(simple_lake_coords):
    """SVG should have a viewBox attribute."""
    svg = generate_editable_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        label="TEST",
        subtitle="",
        fill_color="#1a3a5c",
        border_style=None,
    )
    assert "viewBox=" in svg


def test_editable_svg_no_border(simple_lake_coords):
    """When border_style is None, no border group should appear."""
    svg = generate_editable_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        label="TEST",
        subtitle="",
        fill_color="#1a3a5c",
        border_style=None,
    )
    assert '<g id="border">' not in svg


def test_cut_svg_has_no_text(simple_lake_coords):
    """Cut-ready SVG should have no text elements."""
    svg = generate_cut_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        fill_color="#1a3a5c",
        border_style="dotted",
    )
    assert "<text" not in svg


def test_cut_svg_uses_evenodd(simple_lake_coords):
    """Cut SVG should use fill-rule='evenodd'."""
    svg = generate_cut_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        fill_color="#1a3a5c",
        border_style=None,
    )
    assert 'fill-rule="evenodd"' in svg


def test_cut_svg_is_valid_xml(simple_lake_coords):
    """Cut SVG should be parseable XML."""
    import xml.etree.ElementTree as ET
    svg = generate_cut_svg(
        ext_coords=simple_lake_coords,
        island_coords=[],
        fill_color="#1a3a5c",
        border_style=None,
    )
    ET.fromstring(svg)  # raises ParseError if invalid
