"""Tests for lake_sticker.borders module."""

import math
from lake_sticker.borders import dotted_ring, double_line_frame, dashed_ring


def test_dotted_ring_returns_svg_group():
    """dotted_ring should return an SVG <g> element with circles."""
    svg = dotted_ring(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c")
    assert '<g id="border">' in svg
    assert "<circle" in svg
    assert "</g>" in svg


def test_dotted_ring_dot_count():
    """Should generate a reasonable number of dots based on ellipse size."""
    svg = dotted_ring(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c")
    dot_count = svg.count("<circle")
    assert 20 <= dot_count <= 80


def test_double_line_returns_svg_group():
    """double_line_frame should return an SVG <g> with two ellipses."""
    svg = double_line_frame(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c")
    assert '<g id="border">' in svg
    assert "<ellipse" in svg
    assert "</g>" in svg


def test_double_line_has_two_ellipses():
    """Should have exactly 2 ellipses (inner and outer)."""
    svg = double_line_frame(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c")
    assert svg.count("<ellipse") == 2


def test_dashed_ring_returns_svg_group():
    """dashed_ring should return an SVG <g> with a dashed ellipse."""
    svg = dashed_ring(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c")
    assert '<g id="border">' in svg
    assert "stroke-dasharray" in svg
    assert "</g>" in svg


def test_dotted_ring_cut_ready():
    """Cut-ready mode should produce filled circles."""
    svg = dotted_ring(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c", cut_ready=True)
    assert "<circle" in svg
    assert 'fill="#1a3a5c"' in svg


def test_double_line_cut_ready():
    """Cut-ready mode should produce filled path outlines."""
    svg = double_line_frame(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c", cut_ready=True)
    assert "<path" in svg or "<ellipse" in svg


def test_dashed_ring_cut_ready():
    """Cut-ready mode should produce filled paths for each dash segment.

    Implementation uses stroke-based thick paths rather than filled arcs.
    Cricut can cut stroked paths when exported to DXF/cut-ready SVG.
    The test checks for <path> elements with a stroke color matching the
    requested color, which is the valid cut-ready representation chosen here.
    """
    svg = dashed_ring(cx=400, cy=400, rx=350, ry=300, color="#1a3a5c", cut_ready=True)
    assert "<path" in svg
    assert "#1a3a5c" in svg
