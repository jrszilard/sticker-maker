"""SVG composition module for map stickers.

Assembles processed map features — roads, water, green spaces, buildings,
icons, labels, borders, and titles — into editable and cut-ready SVG
documents.
"""

import random
import xml.etree.ElementTree as ET

from lake_sticker.geometry import compute_projection, coords_to_svg_path
from lake_sticker.borders import RECT_BORDER_STYLES
from lake_sticker.map.icons import load_icon_mapping, resolve_icon, load_icon_svg
from lake_sticker.map.layout import resolve_icon_collisions

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANVAS_WIDTH = 800
PADDING = 60
LABEL_FONT = "Georgia, 'Times New Roman', serif"

DEFAULT_COLORS = {
    "background": "#faf6f0",
    "water": "#7eb8cc",
    "water_waves": "#9dd0e0",
    "green": "#5a8f4a",
    "road_fill": "#c9b88a",
    "road_outline": "#d4c5a0",
    "building": "#d4816b",
    "label": "#3d405b",
    "title": "#3d405b",
}

# Road stroke widths: (outline_width, fill_width)
ROAD_WIDTHS = {
    "primary":     (10, 7),
    "secondary":   (7, 5),
    "residential": (5, 3),
    "footway":     (0, 1.5),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _merged_colors(colors):
    """Return DEFAULT_COLORS updated with any overrides from *colors*."""
    c = dict(DEFAULT_COLORS)
    if colors:
        c.update(colors)
    return c


def _compute_canvas(bounds):
    """Return (canvas_w, canvas_h) from geographic bounds.

    Width is fixed at CANVAS_WIDTH; height is derived from the aspect ratio
    of the bounding box plus 2*PADDING.
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    lon_span = max_lon - min_lon
    lat_span = max_lat - min_lat

    if lon_span == 0:
        lon_span = 0.001
    if lat_span == 0:
        lat_span = 0.001

    aspect = lat_span / lon_span
    available_w = CANVAS_WIDTH - 2 * PADDING
    canvas_h = int(available_w * aspect) + 2 * PADDING
    return CANVAS_WIDTH, canvas_h


def _polygon_to_svg_path(polygon, bounds, canvas_w, canvas_h):
    """Convert a Shapely Polygon (with possible holes) to an SVG path string."""
    exterior = list(polygon.exterior.coords)
    path = coords_to_svg_path(exterior, bounds, canvas_w, canvas_h, PADDING, close=True)
    for interior in polygon.interiors:
        hole = list(interior.coords)
        path += " " + coords_to_svg_path(hole, bounds, canvas_w, canvas_h, PADDING, close=True)
    return path


def _linestring_to_svg_path(coords, bounds, canvas_w, canvas_h):
    """Convert a coordinate list to a non-closed SVG path string."""
    return coords_to_svg_path(coords, bounds, canvas_w, canvas_h, PADDING, close=False)


def _extract_icon_body(svg_text):
    """Extract the inner content of an SVG element (strip the outer <svg> tag).

    Returns the inner XML string suitable for embedding inside a <g> or <symbol>.
    """
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return svg_text

    # Collect all child elements as strings
    parts = []
    for child in root:
        parts.append(ET.tostring(child, encoding="unicode"))
    return "\n".join(parts)


def _svg_icon_viewbox(svg_text):
    """Extract the viewBox attribute from an SVG icon (default '0 0 40 40')."""
    try:
        root = ET.fromstring(svg_text)
        return root.get("viewBox", "0 0 40 40")
    except ET.ParseError:
        return "0 0 40 40"


# ---------------------------------------------------------------------------
# Layer renderers
# ---------------------------------------------------------------------------

def _render_background(canvas_w, canvas_h, color):
    lines = [f'  <g id="background">']
    lines.append(
        f'    <rect x="0" y="0" width="{canvas_w}" height="{canvas_h}" '
        f'fill="{color}" stroke="none"/>'
    )
    lines.append("  </g>")
    return "\n".join(lines)


def _render_green_layer(green_features, bounds, canvas_w, canvas_h, colors):
    """Render green-space polygons with scattered tree circles."""
    lines = ['  <g id="green">']
    rng = random.Random(42)
    green_color = colors["green"]

    for feature in green_features:
        geom = feature.get("geometry")
        if geom is None or geom.geom_type not in ("Polygon", "MultiPolygon"):
            continue

        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for poly in polys:
            path_d = _polygon_to_svg_path(poly, bounds, canvas_w, canvas_h)
            lines.append(
                f'    <path d="{path_d}" fill="{green_color}" fill-opacity="0.45" '
                f'fill-rule="evenodd" stroke="none"/>'
            )

            # Scatter small circles inside the polygon
            minx, miny, maxx, maxy = poly.bounds
            project = compute_projection(bounds, canvas_w, canvas_h, PADDING)
            attempts = 0
            placed = 0
            max_circles = 15
            while placed < max_circles and attempts < max_circles * 10:
                attempts += 1
                lon = rng.uniform(minx, maxx)
                lat = rng.uniform(miny, maxy)
                from shapely.geometry import Point as ShapelyPoint
                if poly.contains(ShapelyPoint(lon, lat)):
                    cx, cy = project(lon, lat)
                    r = rng.uniform(3, 6)
                    lines.append(
                        f'    <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                        f'fill="{green_color}" fill-opacity="0.65" stroke="none"/>'
                    )
                    placed += 1

    lines.append("  </g>")
    return "\n".join(lines)


def _render_water_layer(water_features, bounds, canvas_w, canvas_h, colors):
    """Render water polygons with decorative wave lines inside."""
    lines = ['  <g id="water">']
    water_color = colors["water"]
    wave_color = colors["water_waves"]

    for feature in water_features:
        geom = feature.get("geometry")
        if geom is None or geom.geom_type not in ("Polygon", "MultiPolygon"):
            continue

        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for poly in polys:
            path_d = _polygon_to_svg_path(poly, bounds, canvas_w, canvas_h)
            lines.append(
                f'    <path d="{path_d}" fill="{water_color}" fill-rule="evenodd" stroke="none"/>'
            )

            # Decorative wave lines inside the polygon
            project = compute_projection(bounds, canvas_w, canvas_h, PADDING)
            minx, miny, maxx, maxy = poly.bounds

            lat_span = maxy - miny
            step_lat = lat_span * 0.15
            if step_lat <= 0:
                continue

            lat = miny + step_lat
            while lat < maxy:
                # Compute horizontal extent at this latitude
                # Use a simple horizontal line clipped to polygon bounds
                px_left, py = project(minx, lat)
                px_right, _ = project(maxx, lat)

                if px_right > px_left:
                    # Simple quadratic wave
                    mid_x = (px_left + px_right) / 2
                    ctrl_y = py - 4
                    lines.append(
                        f'    <path d="M {px_left:.1f},{py:.1f} '
                        f'Q {mid_x:.1f},{ctrl_y:.1f} {px_right:.1f},{py:.1f}" '
                        f'fill="none" stroke="{wave_color}" stroke-width="1" '
                        f'stroke-opacity="0.6"/>'
                    )

                lat += step_lat

    lines.append("  </g>")
    return "\n".join(lines)


def _render_roads_layer(road_features, bounds, canvas_w, canvas_h, colors):
    """Render roads using two-stroke technique."""
    lines = ['  <g id="roads">']
    road_fill = colors["road_fill"]
    road_outline = colors["road_outline"]

    # Two passes: outline first, then fill
    # Pass 1: outline strokes
    for feature in road_features:
        road_class = feature.get("road_class", "residential")
        outline_w, fill_w = ROAD_WIDTHS.get(road_class, (5, 3))
        if outline_w == 0:
            continue

        geom = feature["geometry"]
        if feature.get("smoothed_coords"):
            coords = feature["smoothed_coords"]
        elif geom.geom_type == "Polygon":
            coords = list(geom.exterior.coords)
        elif hasattr(geom, "coords"):
            coords = list(geom.coords)
        else:
            continue
        if len(coords) < 2:
            continue

        path_d = _linestring_to_svg_path(coords, bounds, canvas_w, canvas_h)
        lines.append(
            f'    <path d="{path_d}" fill="none" stroke="{road_outline}" '
            f'stroke-width="{outline_w}" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    # Pass 2: fill strokes on top
    for feature in road_features:
        road_class = feature.get("road_class", "residential")
        outline_w, fill_w = ROAD_WIDTHS.get(road_class, (5, 3))

        geom = feature["geometry"]
        if feature.get("smoothed_coords"):
            coords = feature["smoothed_coords"]
        elif geom.geom_type == "Polygon":
            coords = list(geom.exterior.coords)
        elif hasattr(geom, "coords"):
            coords = list(geom.coords)
        else:
            continue
        if len(coords) < 2:
            continue

        path_d = _linestring_to_svg_path(coords, bounds, canvas_w, canvas_h)

        if road_class == "footway":
            lines.append(
                f'    <path d="{path_d}" fill="none" stroke="{road_fill}" '
                f'stroke-width="{fill_w}" stroke-dasharray="4 3" '
                f'stroke-linecap="round" stroke-linejoin="round"/>'
            )
        else:
            lines.append(
                f'    <path d="{path_d}" fill="none" stroke="{road_fill}" '
                f'stroke-width="{fill_w}" stroke-linecap="round" stroke-linejoin="round"/>'
            )

    lines.append("  </g>")
    return "\n".join(lines)


def _render_buildings_layer(building_features, bounds, canvas_w, canvas_h, colors):
    """Render building footprints as simplified rectangles."""
    lines = ['  <g id="buildings">']
    building_color = colors["building"]

    for feature in building_features:
        geom = feature.get("geometry")
        if geom is None or geom.geom_type != "Polygon":
            continue

        path_d = _polygon_to_svg_path(geom, bounds, canvas_w, canvas_h)
        lines.append(
            f'    <path d="{path_d}" fill="{building_color}" fill-opacity="0.8" '
            f'fill-rule="evenodd" stroke="{building_color}" stroke-width="0.5" '
            f'stroke-opacity="0.5"/>'
        )

    lines.append("  </g>")
    return "\n".join(lines)


def _render_icons_layer(poi_features, bounds, canvas_w, canvas_h, colors):
    """Render POI icons using <defs> + <use> pattern with collision avoidance."""
    icon_size = 40
    project = compute_projection(bounds, canvas_w, canvas_h, PADDING)
    mapping = load_icon_mapping()

    # Build icon list with projected positions
    icon_items = []
    for poi in poi_features:
        geom = poi.get("geometry")
        if geom is None:
            continue

        # Get the point coordinates
        if geom.geom_type == "Point":
            lon, lat = geom.x, geom.y
        elif geom.geom_type == "Polygon":
            c = geom.centroid
            lon, lat = c.x, c.y
        else:
            continue

        cx, cy = project(lon, lat)

        # Resolve icon name
        icon_name = poi.get("icon") or resolve_icon(poi.get("osm_tags", {}), mapping)

        icon_items.append({
            "x": cx,
            "y": cy,
            "icon": icon_name,
            "name": poi.get("name", ""),
            "importance": poi.get("importance", 0),
        })

    # Collision avoidance
    if icon_items:
        icon_items = resolve_icon_collisions(icon_items, icon_size=icon_size,
                                             canvas_w=canvas_w, canvas_h=canvas_h)

    # Gather unique icon names
    used_icons = {item["icon"] for item in icon_items}

    lines = ['  <g id="icons">']

    # Emit <defs> with <symbol> elements for each unique icon
    if used_icons:
        lines.append("    <defs>")
        for icon_name in sorted(used_icons):
            try:
                svg_text = load_icon_svg(icon_name)
            except FileNotFoundError:
                try:
                    svg_text = load_icon_svg("pin")
                except FileNotFoundError:
                    continue

            vb = _svg_icon_viewbox(svg_text)
            body = _extract_icon_body(svg_text)
            lines.append(
                f'      <symbol id="icon-{icon_name}" viewBox="{vb}">'
            )
            lines.append(f'        {body}')
            lines.append("      </symbol>")
        lines.append("    </defs>")

    # Emit <use> instances
    half = icon_size / 2
    for item in icon_items:
        x = item["x"] - half
        y = item["y"] - half
        icon_name = item["icon"]
        lines.append(
            f'    <use href="#icon-{icon_name}" x="{x:.1f}" y="{y:.1f}" '
            f'width="{icon_size}" height="{icon_size}"/>'
        )

    lines.append("  </g>")
    return "\n".join(lines)


def _render_title_layer(title, subtitle, canvas_w, canvas_h, colors):
    """Render title and subtitle text centered below the map."""
    lines = ['  <g id="title">']
    title_color = colors["title"]
    cx = canvas_w // 2
    # Place title in the lower portion of the canvas
    title_y = canvas_h - 30
    subtitle_y = canvas_h - 10

    if title:
        lines.append(
            f'    <text x="{cx}" y="{title_y}" text-anchor="middle" '
            f'font-family="{LABEL_FONT}" font-weight="700" font-size="28" '
            f'fill="{title_color}" letter-spacing="3">{title}</text>'
        )
    if subtitle:
        lines.append(
            f'    <text x="{cx}" y="{subtitle_y}" text-anchor="middle" '
            f'font-family="{LABEL_FONT}" font-weight="400" font-size="14" '
            f'fill="{title_color}" letter-spacing="5">{subtitle}</text>'
        )

    lines.append("  </g>")
    return "\n".join(lines)


def _render_border(border_style, canvas_w, canvas_h, colors, cut_ready=False):
    """Render a rectangular border on top of all map content."""
    if not border_style or border_style not in RECT_BORDER_STYLES:
        return ""

    border_fn = RECT_BORDER_STYLES[border_style]
    border_color = colors.get("title", DEFAULT_COLORS["title"])
    margin = PADDING // 2
    x = margin
    y = margin
    w = canvas_w - 2 * margin
    h = canvas_h - 2 * margin

    return border_fn(x=x, y=y, w=w, h=h, color=border_color, cut_ready=cut_ready)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_map_editable_svg(
    features,
    bounds,
    title,
    subtitle,
    colors=None,
    border_style=None,
    label_style="none",
):
    """Generate an editable, layered SVG map document.

    Parameters
    ----------
    features    : dict with keys roads, water, green, buildings, pois
    bounds      : (min_lon, min_lat, max_lon, max_lat)
    title       : main title text
    subtitle    : secondary title text
    colors      : optional color override dict (merged with DEFAULT_COLORS)
    border_style: one of 'dotted', 'double_line', 'dashed', or None
    label_style : 'none' or 'legend'

    Returns
    -------
    str : SVG document as a string
    """
    c = _merged_colors(colors)
    canvas_w, canvas_h = _compute_canvas(bounds)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" '
        f'width="{canvas_w}" height="{canvas_h}">',
        f'  <!-- Generated from OpenStreetMap data. (c) OpenStreetMap contributors -->',
    ]

    # Layer 1: Background
    parts.append(_render_background(canvas_w, canvas_h, c["background"]))

    # Layer 2: Green spaces
    parts.append(_render_green_layer(
        features.get("green", []), bounds, canvas_w, canvas_h, c
    ))

    # Layer 3: Water
    parts.append(_render_water_layer(
        features.get("water", []), bounds, canvas_w, canvas_h, c
    ))

    # Layer 4: Roads
    parts.append(_render_roads_layer(
        features.get("roads", []), bounds, canvas_w, canvas_h, c
    ))

    # Layer 5: Buildings
    parts.append(_render_buildings_layer(
        features.get("buildings", []), bounds, canvas_w, canvas_h, c
    ))

    # Layer 6: Icons (defs + use)
    parts.append(_render_icons_layer(
        features.get("pois", []), bounds, canvas_w, canvas_h, c
    ))

    # Layer 7: Labels / legend (if requested)
    if label_style == "legend":
        pois = features.get("pois", [])
        if pois:
            from lake_sticker.map.layout import build_legend
            legend = build_legend(pois)
            label_color = c["label"]
            lines = ['  <g id="labels">']
            legend_x = 10
            legend_y = canvas_h - (len(legend) * 18 + 10)
            for entry in legend:
                lines.append(
                    f'    <text x="{legend_x}" y="{legend_y}" '
                    f'font-family="{LABEL_FONT}" font-size="11" '
                    f'fill="{label_color}">'
                    f'{entry["number"]}. {entry["name"]}</text>'
                )
                legend_y += 18
            lines.append("  </g>")
            parts.append("\n".join(lines))

    # Layer 8: Title / subtitle
    parts.append(_render_title_layer(title, subtitle, canvas_w, canvas_h, c))

    # Layer 9: Border (on top of all map content)
    border_svg = _render_border(border_style, canvas_w, canvas_h, c, cut_ready=False)
    if border_svg:
        parts.append(border_svg)

    parts.append("</svg>")
    return "\n".join(parts)


def generate_map_cut_svg(bounds, border_style=None, colors=None):
    """Generate a cut-ready SVG containing only the border outline.

    No map content, no text — just the cut path for a vinyl cutter.

    Parameters
    ----------
    bounds       : (min_lon, min_lat, max_lon, max_lat)
    border_style : one of 'dotted', 'double_line', 'dashed', or None
    colors       : optional color override dict

    Returns
    -------
    str : SVG document as a string
    """
    c = _merged_colors(colors)
    canvas_w, canvas_h = _compute_canvas(bounds)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" '
        f'width="{canvas_w}" height="{canvas_h}">',
    ]

    # Border only — cut-ready mode
    border_svg = _render_border(border_style, canvas_w, canvas_h, c, cut_ready=True)
    if border_svg:
        parts.append(border_svg)

    parts.append("</svg>")
    return "\n".join(parts)
