"""Reprojection and the single shared meters->SVG transform.

The shared ``scale`` (SVG units per metre) is what guarantees puzzle-fit: the
base map and every sticker apply the *same* scale, differing only in translate.
"""

from shapely.ops import transform as shapely_transform


def to_meters(geom, dst_epsg=32110, src_epsg=4269):
    """Reproject a shapely geometry from lat/lon to a metre-based CRS.

    Default destination is NH State Plane (EPSG:32110, metres).
    """
    from pyproj import Transformer

    transformer = Transformer.from_crs(
        f"EPSG:{src_epsg}", f"EPSG:{dst_epsg}", always_xy=True
    )
    return shapely_transform(transformer.transform, geom)


def to_meters_feature_set(feature_set, dst_epsg=32110, src_epsg=4269) -> dict:
    """Return a copy of *feature_set* with all geometries reprojected to metres."""
    townships = [
        {**t, "geometry": to_meters(t["geometry"], dst_epsg, src_epsg)}
        for t in feature_set["townships"]
    ]
    counties = [
        {**c, "geometry": to_meters(c["geometry"], dst_epsg, src_epsg)}
        for c in feature_set["counties"]
    ]
    state = to_meters(feature_set["state"], dst_epsg, src_epsg)
    return {"townships": townships, "counties": counties, "state": state}


def compute_scale(bounds_m, printable_w, printable_h) -> float:
    """SVG units per metre so the bounds fit within printable_w x printable_h."""
    minx, miny, maxx, maxy = bounds_m
    span_x = (maxx - minx) or 1.0
    span_y = (maxy - miny) or 1.0
    return min(printable_w / span_x, printable_h / span_y)


def make_projector(scale, origin_x, origin_y, offset_x, offset_y, canvas_h):
    """Return a function mapping metre coords to SVG coords (y flipped down)."""

    def project(x, y):
        sx = offset_x + (x - origin_x) * scale
        sy = canvas_h - (offset_y + (y - origin_y) * scale)
        return (round(sx, 2), round(sy, 2))

    return project


def iter_polygons(geom):
    """Yield Polygon parts of a Polygon or MultiPolygon (empty for others)."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    return []


def _ring_to_path(coords) -> str:
    parts = []
    for i, (x, y) in enumerate(coords):
        parts.append(f"{'M' if i == 0 else 'L'} {x},{y}")
    parts.append("Z")
    return " ".join(parts)


def polygon_to_path(polygon, project) -> str:
    """Build an SVG path (with holes) from a shapely Polygon and a projector."""
    d = _ring_to_path([project(x, y) for x, y in polygon.exterior.coords])
    for interior in polygon.interiors:
        d += " " + _ring_to_path([project(x, y) for x, y in interior.coords])
    return d
