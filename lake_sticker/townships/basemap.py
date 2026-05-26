"""Render the New Hampshire base-map poster SVG."""

from xml.sax.saxutils import escape

from lake_sticker.townships.projection import (
    iter_polygons,
    make_projector,
    polygon_to_path,
)

SERIF = "Georgia, 'Times New Roman', serif"
INK = "#3d405b"

# A town whose projected width is below this (SVG units) gets a numbered marker
# and a legend entry instead of an inline name label.
MIN_LABEL_WIDTH = 36.0


def _font_size_for_width(width_units: float) -> float:
    """Pick a label font size from the polygon's projected width."""
    return max(7.0, min(14.0, width_units / 10.0))


def render_basemap(feature_set_m, scale, poster_w=2304, poster_h=3456, margin=96) -> str:
    """Render the poster from a metres-based feature set and shared *scale*.

    Geometries in *feature_set_m* must already be in metres (see
    ``projection.to_meters_feature_set``). The same *scale* is reused for the
    stickers so they register against the map.
    """
    state = feature_set_m["state"]
    minx, miny, maxx, maxy = state.bounds
    printable_w = poster_w - 2 * margin
    printable_h = poster_h - 2 * margin
    used_w = (maxx - minx) * scale
    used_h = (maxy - miny) * scale
    offset_x = margin + (printable_w - used_w) / 2
    offset_y = margin + (printable_h - used_h) / 2
    project = make_projector(scale, minx, miny, offset_x, offset_y, poster_h)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {poster_w} {poster_h}" width="24in" height="36in">',
        "  <!-- Source: U.S. Census Bureau TIGER/Line -->",
    ]

    # Townships (thin outlines, no fill).
    parts.append(f'  <g id="townships" fill="none" stroke="{INK}" stroke-width="1">')
    for t in feature_set_m["townships"]:
        for poly in iter_polygons(t["geometry"]):
            parts.append(f'    <path d="{polygon_to_path(poly, project)}"/>')
    parts.append("  </g>")

    # Counties (medium outlines).
    parts.append(f'  <g id="counties" fill="none" stroke="{INK}" stroke-width="3">')
    for c in feature_set_m["counties"]:
        for poly in iter_polygons(c["geometry"]):
            parts.append(f'    <path d="{polygon_to_path(poly, project)}"/>')
    parts.append("  </g>")

    # State (thick outline).
    parts.append(f'  <g id="state" fill="none" stroke="{INK}" stroke-width="6">')
    for poly in iter_polygons(state):
        parts.append(f'    <path d="{polygon_to_path(poly, project)}"/>')
    parts.append("  </g>")

    # Labels: inline name when the town is big enough, else a numbered marker.
    legend = []
    parts.append(
        f'  <g id="labels" fill="{INK}" font-family="{SERIF}" text-anchor="middle">'
    )
    for t in feature_set_m["townships"]:
        geom = t["geometry"]
        gminx, gminy, gmaxx, gmaxy = geom.bounds
        width_units = (gmaxx - gminx) * scale
        pt = geom.representative_point()
        x, y = project(pt.x, pt.y)
        if width_units >= MIN_LABEL_WIDTH:
            fs = _font_size_for_width(width_units)
            parts.append(
                f'    <text x="{x}" y="{y}" font-size="{fs:.1f}">'
                f"{escape(t['name'])}</text>"
            )
        else:
            number = len(legend) + 1
            legend.append((number, t["name"]))
            parts.append(
                f'    <text x="{x}" y="{y}" font-size="7">{number}</text>'
            )
    parts.append("  </g>")

    # Legend block for numbered (too-small) towns, lower-left margin.
    if legend:
        parts.append(
            f'  <g id="legend" fill="{INK}" font-family="{SERIF}" font-size="10">'
        )
        lx = margin
        ly = poster_h - margin - len(legend) * 14
        for number, name in legend:
            parts.append(
                f'    <text x="{lx}" y="{ly}">{number}. {escape(name)}</text>'
            )
            ly += 14
        parts.append("  </g>")

    # Title.
    parts.append('  <g id="title">')
    parts.append(
        f'    <text x="{poster_w / 2}" y="{margin}" text-anchor="middle" '
        f'font-family="{SERIF}" font-size="64" font-weight="700" '
        f'fill="{INK}" letter-spacing="6">NEW HAMPSHIRE</text>'
    )
    parts.append("  </g>")

    parts.append("</svg>")
    return "\n".join(parts)
