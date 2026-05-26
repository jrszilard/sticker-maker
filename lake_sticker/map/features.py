"""Process and simplify map features for sticker rendering."""

from shapely.geometry import LineString, Polygon, Point
from shapely import simplify as shapely_simplify

_ROAD_CLASSES = {
    "motorway": "primary", "motorway_link": "primary",
    "trunk": "primary", "trunk_link": "primary",
    "primary": "primary", "primary_link": "primary",
    "secondary": "secondary", "secondary_link": "secondary",
    "tertiary": "secondary", "tertiary_link": "secondary",
    "residential": "residential", "living_street": "residential",
    "unclassified": "residential",
    "pedestrian": "footway", "footway": "footway",
    "path": "footway", "cycleway": "footway", "track": "footway",
}

_EXCLUDED_ROADS = {"service", "construction", "proposed", "raceway", "bus_guideway"}


def chaikin_smooth(coords, iterations=2):
    """Smooth a coordinate list using Chaikin's corner-cutting algorithm."""
    for _ in range(iterations):
        if len(coords) < 2:
            return coords
        new_coords = []
        for i in range(len(coords) - 1):
            x0, y0 = coords[i]
            x1, y1 = coords[i + 1]
            new_coords.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
            new_coords.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
        coords = new_coords
    return coords


def classify_road(tags):
    """Classify a road by its highway tag. Returns class or None if excluded."""
    highway = tags.get("highway", "")
    if highway in _EXCLUDED_ROADS:
        return None
    return _ROAD_CLASSES.get(highway)


def filter_roads(features):
    """Filter road features, dropping excluded types."""
    result = []
    for f in features:
        if f["type"] != "road":
            continue
        classification = classify_road(f["osm_tags"])
        if classification is not None:
            f["road_class"] = classification
            result.append(f)
    return result


def simplify_buildings(features, min_area=0.0000005):
    """Filter buildings by minimum area, dropping tiny structures."""
    result = []
    for f in features:
        if f["type"] != "building":
            continue
        if f["geometry"].geom_type == "Polygon" and f["geometry"].area >= min_area:
            result.append(f)
    return result


def _smooth_roads(roads, tolerance=0.00005):
    """Simplify and smooth road geometries."""
    for road in roads:
        geom = road["geometry"]
        if geom.geom_type == "LineString":
            simplified = shapely_simplify(geom, tolerance=tolerance, preserve_topology=True)
            coords = list(simplified.coords)
            smoothed = chaikin_smooth(coords, iterations=2)
            road["geometry"] = LineString(smoothed)
            road["smoothed_coords"] = smoothed
    return roads


def process_map_features(features):
    """Process raw features into categorized, simplified groups.

    Returns dict with keys: roads, water, green, buildings, pois
    """
    roads = filter_roads([f for f in features if f["type"] == "road"])
    roads = _smooth_roads(roads)

    water = [f for f in features if f["type"] == "water"]
    green = [f for f in features if f["type"] == "green"]
    buildings = simplify_buildings([f for f in features if f["type"] == "building"])
    pois = [f for f in features if f["type"] == "poi"]

    # Promote typed buildings to POIs
    promoted = []
    remaining_buildings = []
    for b in buildings:
        tags = b["osm_tags"]
        building_type = tags.get("building", "yes")
        if building_type in ("church", "cathedral", "chapel", "mosque",
                             "museum", "hotel", "school", "hospital"):
            b["type"] = "poi"
            b["geometry"] = b["geometry"].centroid
            promoted.append(b)
        else:
            remaining_buildings.append(b)

    pois.extend(promoted)

    return {
        "roads": roads,
        "water": water,
        "green": green,
        "buildings": remaining_buildings,
        "pois": pois,
    }
