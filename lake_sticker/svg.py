"""SVG assembly for lake sticker output.

Generates two variants:
- Editable: named groups, separate elements, text labels
- Cut-ready: single paths, fill-rule evenodd, no text
"""

from lake_sticker.geometry import coords_to_svg_path, compute_projection
from lake_sticker.borders import BORDER_STYLES

# Defaults
CANVAS_WIDTH = 800
PADDING = 50
LABEL_FONT = "Georgia, 'Times New Roman', serif"


def _compute_canvas(ext_coords, has_label, has_border):
    """Calculate canvas dimensions and bounds from exterior coordinates."""
    lons = [c[0] for c in ext_coords]
    lats = [c[1] for c in ext_coords]
    margin_lon = (max(lons) - min(lons)) * 0.02
    margin_lat = (max(lats) - min(lats)) * 0.02
    bounds = (
        min(lons) - margin_lon,
        min(lats) - margin_lat,
        max(lons) + margin_lon,
        max(lats) + margin_lat,
    )

    aspect = (bounds[3] - bounds[1]) / (bounds[2] - bounds[0])
    canvas_w = CANVAS_WIDTH
    canvas_h = int(canvas_w * aspect) + 2 * PADDING
    label_space = 80 if has_label else 0
    border_margin = 40 if has_border else 0
    total_h = canvas_h + label_space + border_margin

    return canvas_w, canvas_h, total_h, bounds, border_margin


def _build_lake_path(ext_coords, island_coords, bounds, canvas_w, canvas_h, padding):
    """Build combined lake path data with evenodd fill rule."""
    lake_path = coords_to_svg_path(ext_coords, bounds, canvas_w, canvas_h, padding)
    for ic in island_coords:
        lake_path += " " + coords_to_svg_path(ic, bounds, canvas_w, canvas_h, padding)
    return lake_path


def _compute_border_ellipse(ext_coords, bounds, canvas_w, canvas_h, padding):
    """Calculate the ellipse parameters for the border based on the lake bounds."""
    project = compute_projection(bounds, canvas_w, canvas_h, padding)

    lons = [c[0] for c in ext_coords]
    lats = [c[1] for c in ext_coords]

    # Project the lake bounding box corners
    x_min, y_max = project(min(lons), min(lats))  # y is flipped
    x_max, y_min = project(max(lons), max(lats))

    cx = (x_min + x_max) / 2
    cy = (y_min + y_max) / 2
    rx = (x_max - x_min) / 2 + 30  # margin
    ry = (y_max - y_min) / 2 + 30

    return cx, cy, rx, ry


def generate_editable_svg(ext_coords, island_coords, label, subtitle,
                          fill_color, border_style, label_color=None):
    """Generate an editable SVG with named groups."""
    if label_color is None:
        label_color = fill_color

    has_label = bool(label)
    has_border = border_style is not None
    canvas_w, canvas_h, total_h, bounds, border_margin = _compute_canvas(
        ext_coords, has_label, has_border
    )

    lake_padding = PADDING + (border_margin // 2 if has_border else 0)
    lake_path = _build_lake_path(ext_coords, island_coords, bounds, canvas_w, canvas_h, lake_padding)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {total_h}" '
        f'width="{canvas_w}" height="{total_h}">',
        f'  <!-- Generated from OpenStreetMap data. (c) OpenStreetMap contributors -->',
    ]

    # Border
    if has_border and border_style in BORDER_STYLES:
        cx, cy, rx, ry = _compute_border_ellipse(
            ext_coords, bounds, canvas_w, canvas_h, lake_padding
        )
        border_fn = BORDER_STYLES[border_style]
        parts.append(border_fn(cx=cx, cy=cy, rx=rx, ry=ry, color=fill_color))

    # Lake body
    parts.append('  <g id="lake">')
    parts.append(
        f'    <path id="lake-body" fill="{fill_color}" fill-rule="evenodd" '
        f'stroke="none" d="{lake_path}"/>'
    )
    parts.append("  </g>")

    # Label
    if has_label:
        label_y_base = canvas_h + border_margin
        center_x = canvas_w // 2
        parts.append('  <g id="label">')
        parts.append(
            f'    <text id="title" x="{center_x}" y="{label_y_base + 35}" '
            f'text-anchor="middle" font-family="{LABEL_FONT}" font-weight="700" '
            f'font-size="30" fill="{label_color}" letter-spacing="3">{label}</text>'
        )
        if subtitle:
            parts.append(
                f'    <text id="subtitle" x="{center_x}" y="{label_y_base + 65}" '
                f'text-anchor="middle" font-family="{LABEL_FONT}" font-weight="400" '
                f'font-size="16" fill="{label_color}" letter-spacing="5">{subtitle}</text>'
            )
        parts.append("  </g>")

    parts.append("</svg>")
    return "\n".join(parts)


def generate_cut_svg(ext_coords, island_coords, fill_color, border_style):
    """Generate a cut-ready SVG optimized for vinyl cutters."""
    has_border = border_style is not None
    canvas_w, canvas_h, total_h, bounds, border_margin = _compute_canvas(
        ext_coords, has_label=False, has_border=has_border
    )

    lake_padding = PADDING + (border_margin // 2 if has_border else 0)
    lake_path = _build_lake_path(ext_coords, island_coords, bounds, canvas_w, canvas_h, lake_padding)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {total_h}" '
        f'width="{canvas_w}" height="{total_h}">',
    ]

    # Border (cut-ready mode)
    if has_border and border_style in BORDER_STYLES:
        cx, cy, rx, ry = _compute_border_ellipse(
            ext_coords, bounds, canvas_w, canvas_h, lake_padding
        )
        border_fn = BORDER_STYLES[border_style]
        parts.append(border_fn(cx=cx, cy=cy, rx=rx, ry=ry, color=fill_color, cut_ready=True))

    # Lake path
    parts.append(
        f'  <path fill="{fill_color}" fill-rule="evenodd" stroke="none" d="{lake_path}"/>'
    )

    parts.append("</svg>")
    return "\n".join(parts)
