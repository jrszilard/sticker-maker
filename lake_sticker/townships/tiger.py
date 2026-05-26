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
