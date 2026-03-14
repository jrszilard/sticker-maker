"""Search for lakes using the OpenStreetMap Nominatim API."""

import re
import time
import unicodedata

import requests

USER_AGENT = "lake-sticker-maker/1.0"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Rate-limit tracking for Nominatim (1 req/sec policy)
_last_nominatim_request = 0.0

# OSM classes/types that indicate water features
WATER_CLASSES = {
    ("natural", "water"),
    ("water", "lake"),
    ("water", "reservoir"),
    ("water", "pond"),
    ("place", "lake"),
    ("natural", "lake"),
}


def _is_water_feature(result):
    """Check if a Nominatim result is a water feature."""
    cls = result.get("class", "")
    typ = result.get("type", "")
    return (cls, typ) in WATER_CLASSES


def _parse_display_name(display_name):
    """Parse Nominatim display_name into structured parts.

    Nominatim returns comma-separated: "Lake Name, Town, County, State, Country"
    We extract the lake name (first part) and the location context (rest).
    """
    parts = [p.strip() for p in display_name.split(",")]
    name = parts[0] if parts else "Unknown"
    # Build location display from remaining parts, skip country for US lakes
    location_parts = parts[1:] if len(parts) > 1 else []
    # Remove the last part if it's "USA" or "United States" — redundant for display
    if location_parts and location_parts[-1] in ("USA", "United States", "United States of America"):
        location_parts = location_parts[:-1]
    location_display = ", ".join(location_parts) if location_parts else ""
    return name, location_display


def parse_nominatim_results(raw_results):
    """Parse and filter Nominatim results into structured lake candidates.

    Args:
        raw_results: list of dicts from Nominatim JSON response.

    Returns:
        List of dicts with keys: name, location_display, osm_id, osm_type, bbox.
    """
    candidates = []
    for r in raw_results:
        if not _is_water_feature(r):
            continue
        name, location_display = _parse_display_name(r.get("display_name", ""))
        candidates.append({
            "name": name,
            "location_display": location_display,
            "osm_id": r["osm_id"],
            "osm_type": r["osm_type"],
            "bbox": r.get("boundingbox"),
        })
    return candidates


class SearchError(Exception):
    """Raised when lake search fails."""
    pass


def _throttle_nominatim():
    """Enforce 1 request/second rate limit for Nominatim API."""
    global _last_nominatim_request
    elapsed = time.time() - _last_nominatim_request
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_nominatim_request = time.time()


def search_lakes(query, max_results=15):
    """Search for lakes matching the query string.

    Args:
        query: lake name, optionally with state/location (e.g. "Crystal Lake, NH").
        max_results: maximum number of results to return.

    Returns:
        List of candidate dicts (see parse_nominatim_results).

    Raises:
        SearchError: on network errors or API failures.
    """
    _throttle_nominatim()

    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "json",
                "limit": 50,  # fetch more, we filter client-side
                "addressdetails": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        # Retry once on 429
        if resp.status_code == 429:
            time.sleep(5)
            resp = requests.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "json",
                    "limit": 50,
                    "addressdetails": 1,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
        resp.raise_for_status()
    except requests.ConnectionError:
        raise SearchError(
            "Could not connect to OpenStreetMap. Check your internet connection."
        )
    except requests.Timeout:
        raise SearchError("Search timed out. Try again in a moment.")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            raise SearchError("Rate limited by OpenStreetMap. Wait a minute and try again.")
        raise SearchError(f"Search failed: {e}")

    candidates = parse_nominatim_results(resp.json())
    return candidates[:max_results]


def sanitize_filename(lake_name, location):
    """Create a filesystem-safe filename from lake name and location.

    Transliterates unicode to ASCII, lowercases, replaces non-alphanumeric
    with underscores, and collapses multiple underscores.
    """
    raw = f"{lake_name} {location}"
    # Transliterate to ASCII
    normalized = unicodedata.normalize("NFKD", raw)
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
    # Lowercase, replace non-alphanumeric with underscore
    cleaned = re.sub(r"[^a-z0-9]+", "_", ascii_str.lower())
    # Strip leading/trailing underscores
    return cleaned.strip("_")
