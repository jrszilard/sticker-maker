"""Overpass API data fetching and feature classification for map stickers."""

import json
import logging
from pathlib import Path
from typing import Any

import requests
from shapely.geometry import LineString, Point, Polygon

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Tags that trigger classification as POI for specific leisure subtypes
_POI_LEISURE_VALUES = {"marina", "beach_resort"}

# Tags that trigger classification as green for specific leisure subtypes
_GREEN_LEISURE_VALUES = {"park", "garden"}

# Landuse values that map to green
_GREEN_LANDUSE_VALUES = {"forest", "meadow"}


def build_overpass_query(lat: float, lon: float, radius: int) -> str:
    """Build a compound Overpass QL query for all map features within radius.

    Args:
        lat: Centre latitude.
        lon: Centre longitude.
        radius: Search radius in metres.

    Returns:
        Overpass QL query string.
    """
    around = f"around:{radius},{lat},{lon}"
    query_parts = [
        "[out:json][timeout:60];",
        "(",
        # Roads / paths
        f'  way["highway"]({around});',
        # Waterways (rivers, streams)
        f'  way["waterway"]({around});',
        # Water bodies (lakes, ponds)
        f'  way["natural"="water"]({around});',
        f'  relation["natural"="water"]({around});',
        # Generic water tag
        f'  way["water"]({around});',
        # Green spaces
        f'  way["leisure"="park"]({around});',
        f'  way["leisure"="garden"]({around});',
        f'  way["landuse"="forest"]({around});',
        f'  way["landuse"="meadow"]({around});',
        f'  way["natural"="wood"]({around});',
        # Buildings
        f'  way["building"]({around});',
        # POIs — nodes
        f'  node["amenity"]({around});',
        f'  node["tourism"]({around});',
        f'  node["historic"]({around});',
        f'  node["shop"]({around});',
        f'  node["leisure"="marina"]({around});',
        f'  node["leisure"="beach_resort"]({around});',
        # POIs — ways (e.g. large amenity footprints)
        f'  way["amenity"]({around});',
        f'  way["tourism"]({around});',
        f'  way["historic"]({around});',
        f'  way["leisure"="marina"]({around});',
        f'  way["leisure"="beach_resort"]({around});',
        ");",
        "out geom;",
    ]
    return "\n".join(query_parts)


def _classify_element(tags: dict[str, str]) -> tuple[str, str]:
    """Classify an OSM element into (type, subtype) based on its tags.

    Classification rules are applied in order; first match wins.

    Args:
        tags: OSM tag dict from Overpass response.

    Returns:
        Tuple of (feature_type, subtype_string).
    """
    if "highway" in tags:
        return "road", f"highway_{tags['highway']}"

    if "waterway" in tags:
        return "water", f"waterway_{tags['waterway']}"

    if tags.get("natural") == "water":
        return "water", "natural_water"

    if "water" in tags:
        return "water", f"water_{tags['water']}"

    leisure = tags.get("leisure", "")
    if leisure in _GREEN_LEISURE_VALUES:
        return "green", f"leisure_{leisure}"

    landuse = tags.get("landuse", "")
    if landuse in _GREEN_LANDUSE_VALUES:
        return "green", f"landuse_{landuse}"

    if tags.get("natural") == "wood":
        return "green", "natural_wood"

    if "building" in tags:
        return "building", f"building_{tags['building']}"

    if "amenity" in tags:
        return "poi", f"amenity_{tags['amenity']}"

    if "tourism" in tags:
        return "poi", f"tourism_{tags['tourism']}"

    if "historic" in tags:
        return "poi", f"historic_{tags['historic']}"

    if "shop" in tags:
        return "poi", f"shop_{tags['shop']}"

    if leisure in _POI_LEISURE_VALUES:
        return "poi", f"leisure_{leisure}"

    return "unknown", "unknown"


def _build_geometry(element: dict[str, Any]):
    """Build a Shapely geometry from an Overpass element.

    Supports:
    - node  → Point
    - way   → LineString or Polygon (closed ring)

    Args:
        element: Single Overpass element dict.

    Returns:
        Shapely geometry, or None if it cannot be built.
    """
    elem_type = element.get("type")

    if elem_type == "node":
        lat = element.get("lat")
        lon = element.get("lon")
        if lat is None or lon is None:
            return None
        return Point(lon, lat)

    if elem_type in ("way", "relation"):
        geom_nodes = element.get("geometry", [])
        if not geom_nodes:
            return None
        coords = [(g["lon"], g["lat"]) for g in geom_nodes]
        if len(coords) < 2:
            return None
        # A closed ring with ≥4 points (first == last) is a polygon
        if len(coords) >= 4 and coords[0] == coords[-1]:
            try:
                return Polygon(coords)
            except Exception:
                pass
        return LineString(coords)

    return None


def parse_overpass_elements(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse a list of raw Overpass elements into feature dicts.

    Each returned feature dict has the shape:
        {
            "type":     str,       # road / water / green / building / poi / unknown
            "subtype":  str,       # detailed subtype string
            "name":     str,       # from tags["name"], or ""
            "geometry": Geometry,  # Shapely object
            "osm_tags": dict,      # original OSM tags
        }

    Elements that cannot be classified or have no geometry are silently skipped.

    Args:
        elements: Raw elements list from Overpass JSON response.

    Returns:
        List of feature dicts.
    """
    features = []
    for elem in elements:
        tags = elem.get("tags") or {}
        if not tags:
            continue

        feat_type, subtype = _classify_element(tags)
        if feat_type == "unknown":
            continue

        geometry = _build_geometry(elem)
        if geometry is None:
            continue

        features.append(
            {
                "type": feat_type,
                "subtype": subtype,
                "name": tags.get("name", ""),
                "geometry": geometry,
                "osm_tags": tags,
            }
        )

    return features


def fetch_map_data(
    lat: float,
    lon: float,
    radius: int = 2000,
    cache_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Query the Overpass API and return parsed map features.

    Results are cached in ``cache_dir/.cache/`` as JSON files named
    ``map_{lat:.4f}_{lon:.4f}_{radius}.json``.  On subsequent calls with
    the same parameters the cached file is returned without a network
    request.

    Args:
        lat: Centre latitude.
        lon: Centre longitude.
        radius: Search radius in metres (default 2000).
        cache_dir: Base directory for the ``.cache`` sub-folder.  If None
            the current working directory is used.

    Returns:
        List of feature dicts as produced by :func:`parse_overpass_elements`.
    """
    if cache_dir is None:
        cache_dir = Path(".")
    cache_dir = Path(cache_dir)

    cache_folder = cache_dir / ".cache"
    cache_folder.mkdir(parents=True, exist_ok=True)

    cache_filename = f"map_{lat:.4f}_{lon:.4f}_{radius}.json"
    cache_path = cache_folder / cache_filename

    if cache_path.exists():
        logger.debug("Cache hit: %s", cache_path)
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        return parse_overpass_elements(raw["elements"])

    query = build_overpass_query(lat=lat, lon=lon, radius=radius)
    logger.debug("Fetching Overpass data for (%s, %s) r=%s", lat, lon, radius)

    response = requests.get(
        OVERPASS_URL,
        params={"data": query},
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()

    cache_path.write_text(json.dumps(data), encoding="utf-8")

    return parse_overpass_elements(data["elements"])
