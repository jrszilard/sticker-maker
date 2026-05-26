"""Render a single true-scale die-cut township sticker SVG."""

from xml.sax.saxutils import escape

from lake_sticker.townships.projection import (
    iter_polygons,
    make_projector,
    polygon_to_path,
)

SERIF = "Georgia, 'Times New Roman', serif"
INK = "#3d405b"
CUT = "#ff00ff"  # conventional magenta cut-line colour


def render_sticker(township_m, scale, buffer_m=60.0, margin=8) -> str:
    """Render one township sticker at the shared *scale*.

    *township_m* geometry must be in metres. The cut path is the boundary
    expanded by *buffer_m* metres (the kiss-cut white border); *margin* is
    extra SVG units of padding around the cut inside the viewBox.
    """
    geom = township_m["geometry"]
    cut_geom = geom.buffer(buffer_m)

    minx, miny, maxx, maxy = cut_geom.bounds
    canvas_w = (maxx - minx) * scale + 2 * margin
    canvas_h = (maxy - miny) * scale + 2 * margin
    project = make_projector(scale, minx, miny, margin, margin, canvas_h)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {canvas_w:.2f} {canvas_h:.2f}" '
        f'width="{canvas_w:.2f}" height="{canvas_h:.2f}">',
        f"  <!-- {escape(township_m['name'])}, "
        f"{escape(township_m['county'])} County, NH. "
        f"Source: U.S. Census Bureau TIGER/Line -->",
    ]

    # Cut path (die-cut outline, buffered).
    parts.append(f'  <g id="cut" fill="none" stroke="{CUT}" stroke-width="1">')
    for poly in iter_polygons(cut_geom):
        parts.append(f'    <path d="{polygon_to_path(poly, project)}"/>')
    parts.append("  </g>")

    # Boundary (the real town outline, just inside the cut).
    parts.append(f'  <g id="boundary" fill="none" stroke="{INK}" stroke-width="1.5">')
    for poly in iter_polygons(geom):
        parts.append(f'    <path d="{polygon_to_path(poly, project)}"/>')
    parts.append("  </g>")

    # Name label at the shape's representative point.
    pt = geom.representative_point()
    lx, ly = project(pt.x, pt.y)
    parts.append(f'  <g id="label">')
    parts.append(
        f'    <text x="{lx}" y="{ly}" text-anchor="middle" '
        f'font-family="{SERIF}" font-size="10" font-weight="700" '
        f'fill="{INK}">{escape(township_m["name"])}</text>'
    )
    parts.append("  </g>")

    # Empty artwork group, centred on the shape — drop unique art here.
    parts.append(
        f'  <g id="artwork" transform="translate({lx},{ly})">'
    )
    parts.append("    <!-- Add unique per-town artwork here -->")
    parts.append("  </g>")

    parts.append("</svg>")
    return "\n".join(parts)
