"""Tests for lake_sticker.townships.projection module."""

import pytest
from shapely.geometry import Polygon, MultiPolygon

from lake_sticker.townships import projection as proj


def _box(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def test_compute_scale_fits_smaller_dimension():
    # 1000 wide x 2000 tall meters into 100 x 100 printable -> limited by height.
    scale = proj.compute_scale((0, 0, 1000, 2000), 100, 100)
    assert scale == pytest.approx(0.05)  # 100 / 2000


def test_iter_polygons_handles_both_types():
    poly = _box(0, 0, 1, 1)
    multi = MultiPolygon([poly, _box(2, 2, 3, 3)])
    assert len(proj.iter_polygons(poly)) == 1
    assert len(proj.iter_polygons(multi)) == 2


def test_puzzle_fit_same_scale_yields_same_rendered_size():
    # A town box in meters. Project it as part of the basemap and as a sticker;
    # the rendered width/height must be identical because scale is shared.
    scale = 0.05
    town = _box(500, 500, 700, 900)  # 200m x 400m

    basemap_project = proj.make_projector(
        scale, origin_x=0, origin_y=0, offset_x=10, offset_y=10, canvas_h=200
    )
    sticker_project = proj.make_projector(
        scale, origin_x=500, origin_y=500, offset_x=8, offset_y=8, canvas_h=216
    )

    def bbox(project):
        pts = [project(x, y) for x, y in town.exterior.coords]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (max(xs) - min(xs), max(ys) - min(ys))

    bw, bh = bbox(basemap_project)
    sw, sh = bbox(sticker_project)
    assert bw == pytest.approx(sw)
    assert bh == pytest.approx(sh)
    assert bw == pytest.approx(200 * scale)
    assert bh == pytest.approx(400 * scale)


def test_polygon_to_path_emits_move_line_close():
    project = proj.make_projector(1.0, 0, 0, 0, 0, 10)
    d = proj.polygon_to_path(_box(0, 0, 2, 2), project)
    assert d.startswith("M ")
    assert " L " in d
    assert d.rstrip().endswith("Z")


def test_to_meters_changes_coordinate_magnitude():
    pytest.importorskip("pyproj")
    # A small box near Concord, NH in lat/lon -> metres (State Plane).
    geom = _box(-71.55, 43.18, -71.50, 43.22)
    projected = proj.to_meters(geom)
    minx, miny, maxx, maxy = projected.bounds
    # State Plane NH coordinates are large positive metre values.
    assert maxx - minx > 1000
    assert maxy - miny > 1000
