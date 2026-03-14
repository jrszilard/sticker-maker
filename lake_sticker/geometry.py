"""Fetch and process lake geometry from OpenStreetMap."""

import json
import math
import time
from pathlib import Path

import requests
from shapely.geometry import Polygon, MultiPolygon, shape
from shapely.ops import unary_union
from shapely import simplify as shapely_simplify

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "lake-sticker-maker/1.0"
CACHE_DIR = Path(".cache")


class GeometryError(Exception):
    """Raised when geometry fetch or processing fails."""
    pass


def auto_tolerance(geom):
    """Calculate a simplification tolerance based on lake size.

    Uses ~0.1% of the bounding box diagonal. This gives:
    - Small pond (0.01 deg bbox): tolerance ~0.000014 (~1.5m)
    - Medium lake (0.1 deg bbox): tolerance ~0.00014 (~15m)
    - Large lake (1.0 deg bbox): tolerance ~0.0014 (~155m)
    """
    minx, miny, maxx, maxy = geom.bounds
    diagonal = math.sqrt((maxx - minx) ** 2 + (maxy - miny) ** 2)
    return diagonal * 0.001


def tolerance_to_meters(tolerance, latitude):
    """Approximate conversion from degrees to meters at a given latitude."""
    meters_per_degree = 111_000 * math.cos(math.radians(latitude))
    return tolerance * meters_per_degree


def process_geometry(geom, tolerance=None, min_island_fraction=0.0001):
    """Process raw geometry into exterior coords and island coord lists.

    Args:
        geom: Shapely Polygon or MultiPolygon.
        tolerance: simplification tolerance in degrees. 0 = no simplification.
                   None = auto-calculate.
        min_island_fraction: skip islands smaller than this fraction of lake area.

    Returns:
        Tuple of (exterior_coords, list_of_island_coords).
        Each coords list is [(lon, lat), ...].
    """
    # Union MultiPolygon parts
    if geom.geom_type == "MultiPolygon":
        geom = unary_union(geom)

    # Auto-calculate tolerance if not specified
    if tolerance is None:
        tolerance = auto_tolerance(geom)

    # Simplify
    if tolerance > 0:
        geom = shapely_simplify(geom, tolerance=tolerance, preserve_topology=True)

    # Handle result — union might still produce MultiPolygon
    if geom.geom_type == "MultiPolygon":
        geom = unary_union(geom)
        if geom.geom_type == "MultiPolygon":
            # Still multi — take the largest
            geom = max(geom.geoms, key=lambda p: p.area)

    if geom.geom_type != "Polygon":
        raise GeometryError(f"Expected Polygon, got {geom.geom_type}")

    exterior_coords = list(geom.exterior.coords)
    total_area = geom.area

    # Extract and filter islands
    island_coords = []
    for interior in geom.interiors:
        island_area = Polygon(interior).area
        if total_area > 0 and (island_area / total_area) >= min_island_fraction:
            island_coords.append(list(interior.coords))

    return exterior_coords, island_coords


def compute_projection(bounds, canvas_width, canvas_height, padding):
    """Create a projection function from lon/lat to SVG pixel coords."""
    min_lon, min_lat, max_lon, max_lat = bounds

    available_w = canvas_width - 2 * padding
    available_h = canvas_height - 2 * padding

    scale_x = available_w / (max_lon - min_lon) if max_lon != min_lon else 1
    scale_y = available_h / (max_lat - min_lat) if max_lat != min_lat else 1
    scale = min(scale_x, scale_y)

    actual_w = (max_lon - min_lon) * scale
    actual_h = (max_lat - min_lat) * scale
    offset_x = padding + (available_w - actual_w) / 2
    offset_y = padding + (available_h - actual_h) / 2

    def project(lon, lat):
        x = offset_x + (lon - min_lon) * scale
        y = offset_y + (max_lat - lat) * scale  # flip Y axis
        return (round(x, 2), round(y, 2))

    return project


def coords_to_svg_path(coords, bounds, canvas_width, canvas_height, padding, close=True):
    """Convert lon/lat coordinate list to an SVG path data string."""
    project = compute_projection(bounds, canvas_width, canvas_height, padding)

    parts = []
    for i, (lon, lat) in enumerate(coords):
        x, y = project(lon, lat)
        if i == 0:
            parts.append(f"M {x},{y}")
        else:
            parts.append(f"L {x},{y}")

    if close:
        parts.append("Z")

    return " ".join(parts)


def fetch_geometry(osm_id, osm_type, cache_dir=None):
    """Fetch lake geometry from OSM APIs with local caching.

    Tries in order (Overpass primary since we have exact OSM ID):
    1. Local cache
    2. Overpass API (targeted fetch by OSM ID)
    3. osmnx (if installed)
    4. Nominatim polygon output (last resort)
    """
    if cache_dir is None:
        cache_dir = CACHE_DIR
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_file = cache_dir / f"{osm_type}_{osm_id}.json"

    # Try cache first
    if cache_file.exists():
        try:
            geojson = json.loads(cache_file.read_text())
            return shape(geojson)
        except (json.JSONDecodeError, Exception):
            pass

    # Method 1: Overpass API
    geom = _fetch_via_overpass(osm_id, osm_type)
    if geom is not None:
        _cache_geometry(cache_file, geom)
        return geom

    # Method 2: osmnx (if installed)
    geom = _fetch_via_osmnx(osm_id, osm_type)
    if geom is not None:
        _cache_geometry(cache_file, geom)
        return geom

    # Method 3: Nominatim (last resort)
    geom = _fetch_via_nominatim(osm_id, osm_type)
    if geom is not None:
        _cache_geometry(cache_file, geom)
        return geom

    raise GeometryError(
        f"Could not fetch geometry for {osm_type}/{osm_id}. "
        "Check your internet connection and try again."
    )


def _fetch_via_overpass(osm_id, osm_type):
    """Fetch polygon from Overpass API using exact OSM ID."""
    try:
        if osm_type == "relation":
            query = f"[out:json][timeout:60];relation({osm_id});out geom;"
        elif osm_type == "way":
            query = f"[out:json][timeout:60];way({osm_id});out geom;"
        else:
            return None

        resp = requests.get(OVERPASS_URL, params={"data": query}, timeout=60)
        if resp.status_code == 429:
            time.sleep(5)
            resp = requests.get(OVERPASS_URL, params={"data": query}, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("elements"):
            return None

        element = data["elements"][0]

        if element["type"] == "relation":
            return _assemble_relation_geometry(element)

        if "geometry" in element:
            coords = [(p["lon"], p["lat"]) for p in element["geometry"]]
            if len(coords) >= 4:
                return Polygon(coords)

    except Exception:
        pass
    return None


def _merge_way_segments(segments):
    """Merge way segments that share endpoints into closed rings.

    OSM relations often split a lake boundary across multiple ways.
    This joins ways sharing endpoints (A->B + B->C = A->C) into
    complete closed rings.
    """
    from shapely.ops import linemerge
    from shapely.geometry import LineString, MultiLineString

    if not segments:
        return []

    # Convert coordinate lists to LineStrings
    lines = []
    for seg in segments:
        if len(seg) >= 2:
            lines.append(LineString(seg))

    if not lines:
        return []

    # Use Shapely's linemerge to join connected segments
    merged = linemerge(MultiLineString(lines))

    # Extract closed rings from the result
    rings = []
    if merged.geom_type == "LineString":
        coords = list(merged.coords)
        if coords[0] == coords[-1] and len(coords) >= 4:
            rings.append(coords)
        elif len(coords) >= 4:
            coords.append(coords[0])
            rings.append(coords)
    elif merged.geom_type == "MultiLineString":
        for line in merged.geoms:
            coords = list(line.coords)
            if coords[0] == coords[-1] and len(coords) >= 4:
                rings.append(coords)
            elif len(coords) >= 4:
                coords.append(coords[0])
                rings.append(coords)

    return rings


def _assemble_relation_geometry(element):
    """Assemble a Polygon/MultiPolygon from an Overpass relation element.

    Handles the common OSM case where lake boundaries are split across
    multiple way members that need to be joined end-to-end.
    """
    outer_segments = []
    inner_segments = []

    for member in element.get("members", []):
        if member.get("type") != "way" or "geometry" not in member:
            continue
        coords = [(p["lon"], p["lat"]) for p in member["geometry"]]
        if len(coords) < 2:
            continue

        role = member.get("role", "outer")
        if role == "inner":
            inner_segments.append(coords)
        else:
            outer_segments.append(coords)

    # Merge way segments into closed rings
    outer_rings = _merge_way_segments(outer_segments)
    inner_rings = _merge_way_segments(inner_segments)

    if not outer_rings:
        return None

    if len(outer_rings) == 1:
        return Polygon(outer_rings[0], inner_rings)

    # Multiple outer rings: create polygons and union
    polys = []
    for ring in outer_rings:
        try:
            polys.append(Polygon(ring))
        except Exception:
            continue
    if not polys:
        return None

    multi = MultiPolygon(polys)
    merged = unary_union(multi)

    # Re-attach inner rings if we got a single polygon
    if merged.geom_type == "Polygon" and inner_rings:
        try:
            return Polygon(merged.exterior, inner_rings)
        except Exception:
            return merged

    return merged


def _fetch_via_osmnx(osm_id, osm_type):
    """Fetch geometry using osmnx (if installed)."""
    try:
        import osmnx as ox
        import geopandas  # noqa: F401
        gdf = ox.features_from_place(
            {"osm_id": osm_id, "osm_type": osm_type},
            tags={"natural": "water"},
        )
        if len(gdf) > 0:
            geom = gdf.geometry.iloc[0]
            if geom.geom_type in ("Polygon", "MultiPolygon"):
                return geom
    except ImportError:
        pass
    except Exception:
        pass
    return None


def _fetch_via_nominatim(osm_id, osm_type):
    """Fetch polygon from Nominatim lookup endpoint (last resort)."""
    try:
        type_prefix = osm_type[0].upper()
        resp = requests.get(
            "https://nominatim.openstreetmap.org/lookup",
            params={
                "osm_ids": f"{type_prefix}{osm_id}",
                "format": "geojson",
                "polygon_geojson": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("features"):
            geom = shape(data["features"][0]["geometry"])
            if geom.geom_type in ("Polygon", "MultiPolygon"):
                return geom
    except Exception:
        pass
    return None


def _cache_geometry(cache_file, geom):
    """Cache a geometry as GeoJSON."""
    try:
        from shapely.geometry import mapping
        cache_file.write_text(json.dumps(mapping(geom)))
    except Exception:
        pass
