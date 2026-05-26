"""US Census TIGER/Line data fetching and dissolve for NH townships."""

import datetime
import io
import logging
import zipfile
from pathlib import Path

import requests
from shapely.ops import unary_union

logger = logging.getLogger(__name__)

NH_STATE_FIPS = "33"

# NH county FIPS (3-digit COUNTYFP) -> county name.
NH_COUNTY_NAMES = {
    "001": "Belknap",
    "003": "Carroll",
    "005": "Cheshire",
    "007": "Coos",
    "009": "Grafton",
    "011": "Hillsborough",
    "013": "Merrimack",
    "015": "Rockingham",
    "017": "Strafford",
    "019": "Sullivan",
}


def tiger_cousub_url(year: int) -> str:
    """Return the Census TIGER county-subdivision zip URL for NH and *year*."""
    return (
        f"https://www2.census.gov/geo/tiger/TIGER{year}/COUSUB/"
        f"tl_{year}_{NH_STATE_FIPS}_cousub.zip"
    )


def resolve_tiger_year(current_year=None, max_lookback=3, session=None) -> int:
    """Return the newest published TIGER year, probing with HTTP HEAD.

    Starts at *current_year* and steps back up to *max_lookback* years until a
    cousub release exists. Raises RuntimeError if none is found.
    """
    if current_year is None:
        current_year = datetime.date.today().year
    sess = session or requests

    for year in range(current_year, current_year - max_lookback - 1, -1):
        url = tiger_cousub_url(year)
        try:
            resp = sess.head(url, timeout=30, allow_redirects=True)
        except requests.RequestException:
            continue
        if getattr(resp, "status_code", None) == 200:
            logger.debug("Resolved TIGER year: %s", year)
            return year

    raise RuntimeError(
        f"No published TIGER cousub release found between "
        f"{current_year - max_lookback} and {current_year}."
    )


def download_cousub(year: int, cache_dir) -> Path:
    """Download and extract the NH cousub shapefile; return the .shp path.

    Extracted into ``<cache_dir>/.cache/tiger_<year>_cousub/``. Cached: if the
    .shp already exists it is returned without a network request.
    """
    cache_dir = Path(cache_dir)
    extract_dir = cache_dir / ".cache" / f"tiger_{year}_cousub"
    shp = extract_dir / f"tl_{year}_{NH_STATE_FIPS}_cousub.shp"
    if shp.exists():
        logger.debug("Cache hit: %s", shp)
        return shp

    extract_dir.mkdir(parents=True, exist_ok=True)
    url = tiger_cousub_url(year)
    logger.debug("Downloading %s", url)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(extract_dir)
    return shp


def load_subdivisions(shapefile_path) -> list[dict]:
    """Read the cousub shapefile into plain records (geometry in EPSG:4269)."""
    import geopandas as gpd

    gdf = gpd.read_file(shapefile_path)
    if gdf.crs is not None and gdf.crs.to_epsg() != 4269:
        gdf = gdf.to_crs(epsg=4269)

    records = []
    for _, row in gdf.iterrows():
        records.append(
            {
                "name": row["NAME"],
                "county_fp": row["COUNTYFP"],
                "geometry": row["geometry"],
            }
        )
    return records


def build_feature_set(subdivisions: list[dict]) -> dict:
    """Build townships + dissolved county + state geometries.

    Returns a dict with keys ``townships``, ``counties``, ``state``.
    Geometries are passed through unchanged (caller controls the CRS).
    """
    townships = []
    by_county: dict[str, list] = {}
    for rec in subdivisions:
        fp = rec["county_fp"]
        townships.append(
            {
                "name": rec["name"],
                "county_fp": fp,
                "county": NH_COUNTY_NAMES.get(fp, fp),
                "geometry": rec["geometry"],
            }
        )
        by_county.setdefault(fp, []).append(rec["geometry"])

    counties = []
    for fp in sorted(by_county):
        counties.append(
            {
                "county_fp": fp,
                "name": NH_COUNTY_NAMES.get(fp, fp),
                "geometry": unary_union(by_county[fp]),
            }
        )

    state = unary_union([rec["geometry"] for rec in subdivisions])
    return {"townships": townships, "counties": counties, "state": state}
