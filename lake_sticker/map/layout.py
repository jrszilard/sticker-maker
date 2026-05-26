"""Layout engine for positioning icons and labels on the map."""

import math


def resolve_icon_collisions(icons, icon_size=40, canvas_w=800, canvas_h=600):
    if not icons:
        return icons
    sorted_icons = sorted(icons, key=lambda i: -i.get("importance", 0))
    placed = []
    half = icon_size / 2

    for icon in sorted_icons:
        x, y = icon["x"], icon["y"]
        for placed_icon in placed:
            dx = abs(x - placed_icon["x"])
            dy = abs(y - placed_icon["y"])
            if dx < icon_size * 0.75 and dy < icon_size * 0.75:
                angle = math.atan2(y - placed_icon["y"], x - placed_icon["x"])
                if angle == 0:
                    angle = math.pi / 4
                push = icon_size * 1.1
                x = placed_icon["x"] + push * math.cos(angle)
                y = placed_icon["y"] + push * math.sin(angle)

        x = max(half, min(canvas_w - half, x))
        y = max(half, min(canvas_h - half, y))
        icon["x"] = x
        icon["y"] = y
        placed.append(icon)

    return placed


def build_legend(pois):
    legend = []
    for i, poi in enumerate(pois, 1):
        legend.append({
            "number": i,
            "name": poi.get("name", f"Point {i}"),
            "icon": poi.get("icon", "pin"),
        })
    return legend


def place_road_labels(roads, min_length=50):
    labels = []
    for road in roads:
        name = road.get("name")
        if not name:
            continue
        coords = road.get("smoothed_coords", [])
        if len(coords) < 2:
            continue
        length = 0
        for i in range(len(coords) - 1):
            dx = coords[i + 1][0] - coords[i][0]
            dy = coords[i + 1][1] - coords[i][1]
            length += math.sqrt(dx * dx + dy * dy)
        if length >= min_length:
            labels.append({"name": name, "coords": coords})
    return labels
