"""`nh-map` command: build the NH base map and per-township stickers."""

import argparse
import logging
import re
import unicodedata
from pathlib import Path

from lake_sticker.townships.basemap import render_basemap
from lake_sticker.townships.projection import compute_scale, to_meters_feature_set
from lake_sticker.townships.sticker import render_sticker
from lake_sticker.townships.tiger import (
    build_feature_set,
    download_cousub,
    load_subdivisions,
    resolve_tiger_year,
)

logger = logging.getLogger(__name__)

POSTER_W = 2304   # 24 in * 96
POSTER_H = 3456   # 36 in * 96
MARGIN = 96       # 1 in


def sanitize_filename(name: str) -> str:
    """Lowercase ASCII slug: strip accents/punctuation, spaces -> underscores."""
    ascii_name = (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    ascii_name = ascii_name.lower()
    ascii_name = re.sub(r"['’]", "", ascii_name)   # drop apostrophes before slugging
    ascii_name = re.sub(r"[^a-z0-9]+", "_", ascii_name)
    return ascii_name.strip("_")


def _load_feature_set_m(year, cache_dir):
    """Resolve year, download, read, dissolve, and reproject to metres.

    Isolated so tests can patch it without touching the network or geopandas.
    """
    resolved = year or resolve_tiger_year()
    shp = download_cousub(resolved, cache_dir)
    subdivisions = load_subdivisions(shp)
    feature_set = build_feature_set(subdivisions)
    return to_meters_feature_set(feature_set)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="nh-map",
        description="Generate a New Hampshire base map and township stickers.",
    )
    parser.add_argument("--out-dir", default="output", help="Output directory.")
    parser.add_argument("--cache-dir", default=".", help="Base dir for .cache/.")
    parser.add_argument("--year", type=int, default=None,
                        help="Force a TIGER vintage year (skips auto-resolve).")
    parser.add_argument("--basemap-only", action="store_true",
                        help="Render only the base map poster.")
    parser.add_argument("--no-stickers", action="store_true",
                        help="Alias for --basemap-only.")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fs_m = _load_feature_set_m(args.year, args.cache_dir)
    scale = compute_scale(
        fs_m["state"].bounds, POSTER_W - 2 * MARGIN, POSTER_H - 2 * MARGIN
    )

    basemap_svg = render_basemap(fs_m, scale, POSTER_W, POSTER_H, MARGIN)
    (out_dir / "nh_basemap.svg").write_text(basemap_svg, encoding="utf-8")
    logger.info("Wrote base map (%d townships)", len(fs_m["townships"]))

    if args.basemap_only or args.no_stickers:
        return 0

    stickers_dir = out_dir / "stickers"
    used_stems: dict[Path, set[str]] = {}
    for township in fs_m["townships"]:
        county_dir = stickers_dir / township["county"]
        county_dir.mkdir(parents=True, exist_ok=True)
        svg = render_sticker(township, scale)
        base_stem = sanitize_filename(township["name"])
        county_used = used_stems.setdefault(county_dir, set())
        if base_stem not in county_used:
            stem = base_stem
        else:
            counter = 2
            while f"{base_stem}_{counter}" in county_used:
                counter += 1
            stem = f"{base_stem}_{counter}"
        county_used.add(stem)
        (county_dir / f"{stem}.svg").write_text(svg, encoding="utf-8")

    logger.info("Wrote %d township stickers", len(fs_m["townships"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
