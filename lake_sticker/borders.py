"""Decorative border generators for lake stickers.

Each function generates SVG markup for a border style in two modes:
- Editable: stroked SVG elements (easy to modify in a vector editor)
- Cut-ready: filled paths only (Cricut cuts paths, not strokes)

Note on cut-ready dashed_ring: the cut-ready mode uses stroke-based thick
path segments rather than filled arcs.  A Cricut can cut stroked open paths
when the file is exported as a cut-ready SVG/DXF, so this is a valid
representation.  Using strokes also preserves round line-caps faithfully,
which improves the cut appearance.
"""

import math


def _ellipse_point(cx, cy, rx, ry, angle):
    """Calculate a point on an ellipse at the given angle (radians)."""
    return (
        cx + rx * math.cos(angle),
        cy + ry * math.sin(angle),
    )


def dotted_ring(cx, cy, rx, ry, color, dot_radius=3, cut_ready=False):
    """Generate a ring of evenly-spaced dots around an ellipse.

    Parameters
    ----------
    cx, cy:      centre of the ellipse
    rx, ry:      semi-axes of the ellipse
    color:       fill colour for each dot (hex string, e.g. "#1a3a5c")
    dot_radius:  radius of each dot in SVG user units (default 3)
    cut_ready:   unused — dots are always filled circles; kept for API
                 symmetry with the other generators
    """
    # Approximate ellipse perimeter (Ramanujan's formula)
    h = ((rx - ry) ** 2) / ((rx + ry) ** 2)
    perimeter = math.pi * (rx + ry) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))

    # Use dot_radius * 10 so dots are well-separated; floor at 20 for tiny ellipses.
    spacing = max(dot_radius * 10, 20)
    num_dots = max(12, int(perimeter / spacing))

    parts = ['  <g id="border">']
    for i in range(num_dots):
        angle = 2 * math.pi * i / num_dots
        x, y = _ellipse_point(cx, cy, rx, ry, angle)
        parts.append(
            f'    <circle cx="{x:.1f}" cy="{y:.1f}" r="{dot_radius}" '
            f'fill="{color}" stroke="none"/>'
        )
    parts.append("  </g>")
    return "\n".join(parts)


def double_line_frame(
    cx, cy, rx, ry, color,
    gap=8, inner_width=1.5, outer_width=2.5,
    cut_ready=False,
):
    """Generate two concentric ellipses forming a double-line border.

    Parameters
    ----------
    cx, cy:       centre of the outer ellipse
    rx, ry:       semi-axes of the outer ellipse
    color:        stroke / fill colour
    gap:          distance between the two ellipses (SVG units, default 8)
    inner_width:  stroke width of the inner ellipse (default 1.5)
    outer_width:  stroke width of the outer ellipse (default 2.5)
    cut_ready:    if True, render as filled annular rings instead of strokes
    """
    parts = ['  <g id="border">']

    if cut_ready:
        # Outer ring: filled ellipse with a white ellipse punched out
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" '
            f'rx="{rx + outer_width / 2:.1f}" ry="{ry + outer_width / 2:.1f}" '
            f'fill="{color}" stroke="none"/>'
        )
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" '
            f'rx="{rx - outer_width / 2:.1f}" ry="{ry - outer_width / 2:.1f}" '
            f'fill="white" stroke="none"/>'
        )
        inner_rx = rx - gap
        inner_ry = ry - gap
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" '
            f'rx="{inner_rx + inner_width / 2:.1f}" ry="{inner_ry + inner_width / 2:.1f}" '
            f'fill="{color}" stroke="none"/>'
        )
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" '
            f'rx="{inner_rx - inner_width / 2:.1f}" ry="{inner_ry - inner_width / 2:.1f}" '
            f'fill="white" stroke="none"/>'
        )
    else:
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="{outer_width}"/>'
        )
        inner_rx = rx - gap
        inner_ry = ry - gap
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{inner_rx:.1f}" ry="{inner_ry:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="{inner_width}"/>'
        )

    parts.append("  </g>")
    return "\n".join(parts)


def dashed_ring(
    cx, cy, rx, ry, color,
    dash_length=12, gap_length=8, stroke_width=2,
    cut_ready=False,
):
    """Generate a dashed elliptical border.

    Parameters
    ----------
    cx, cy:        centre of the ellipse
    rx, ry:        semi-axes of the ellipse
    color:         stroke colour
    dash_length:   length of each dash in SVG user units (default 12)
    gap_length:    length of each gap in SVG user units (default 8)
    stroke_width:  width of the dashed stroke (default 2)
    cut_ready:     if True, render each dash as an explicit open <path>
                   with a thick stroke.  Cricut and most cut plotters treat
                   open stroked paths as cut lines, so this is the correct
                   cut-ready representation for dashes.
    """
    parts = ['  <g id="border">']

    if cut_ready:
        # Approximate ellipse perimeter (Ramanujan's formula)
        h = ((rx - ry) ** 2) / ((rx + ry) ** 2)
        perimeter = math.pi * (rx + ry) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))

        total_segment = dash_length + gap_length
        num_segments = max(8, int(perimeter / total_segment))
        dash_fraction = dash_length / total_segment

        for i in range(num_segments):
            start_frac = i / num_segments
            end_frac = start_frac + dash_fraction / num_segments
            start_angle = 2 * math.pi * start_frac
            end_angle = 2 * math.pi * end_frac

            num_points = 6
            path_parts = []
            for j in range(num_points + 1):
                t = start_angle + (end_angle - start_angle) * j / num_points
                x, y = _ellipse_point(cx, cy, rx, ry, t)
                if j == 0:
                    path_parts.append(f"M {x:.1f},{y:.1f}")
                else:
                    path_parts.append(f"L {x:.1f},{y:.1f}")

            path_d = " ".join(path_parts)
            parts.append(
                f'    <path d="{path_d}" fill="none" stroke="{color}" '
                f'stroke-width="{stroke_width}" stroke-linecap="round"/>'
            )
    else:
        parts.append(
            f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="{stroke_width}" '
            f'stroke-dasharray="{dash_length} {gap_length}"/>'
        )

    parts.append("  </g>")
    return "\n".join(parts)


# Map of border style name to function
BORDER_STYLES = {
    "dotted": dotted_ring,
    "double_line": double_line_frame,
    "dashed": dashed_ring,
}
