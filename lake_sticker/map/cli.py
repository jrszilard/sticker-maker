"""Map-specific interactive CLI prompts."""

from lake_sticker.search import search_location, sanitize_filename, SearchError
from lake_sticker.map.fetch import fetch_map_data
from lake_sticker.map.features import process_map_features
from lake_sticker.map.render import generate_map_editable_svg, generate_map_cut_svg
from lake_sticker.cli import _input_with_default, _input_int, _input_yes_no, _unique_path, OUTPUT_DIR

DEFAULT_COLORS = {
    "water": "#7eb8cc",
    "roads": "#c9b88a",
    "green": "#5a8f4a",
    "buildings": "#d4816b",
    "labels": "#3d405b",
}

RADIUS_OPTIONS = {
    1: ("Small (few blocks, ~500m)", 500),
    2: ("Medium (neighborhood, ~1km)", 1000),
    3: ("Large (town center, ~2km)", 2000),
}


def step_search_location():
    """Search for a location and return the selected candidate."""
    while True:
        query = input("\nEnter location (town, city, or address): ").strip()
        if not query:
            continue
        print("\nSearching OpenStreetMap...")
        try:
            candidates = search_location(query)
        except SearchError as e:
            print(f"  Error: {e}")
            continue
        if not candidates:
            print("  No results found. Try a different name or be more specific.")
            continue
        if len(candidates) == 1:
            c = candidates[0]
            print(f"  Found: {c['name']} -- {c['location_display']}")
            if _input_yes_no("  Use this?", default=True):
                return c
            continue
        display_count = min(len(candidates), 15)
        print(f"Found {len(candidates)} results:\n")
        for i, c in enumerate(candidates[:display_count], 1):
            print(f"  {i}) {c['name']} -- {c['location_display']}")
        if len(candidates) > 15:
            print(f"\n  (Showing 15 of {len(candidates)}. Be more specific to narrow results.)")
        idx = _input_int(f"\nSelect a location [1-{display_count}]: ", 1, display_count)
        return candidates[idx - 1]


def step_configure_map(candidate, raw_features):
    """Configure map options."""
    config = {"center": (candidate["lat"], candidate["lon"])}

    category_names = {
        "water": "Water (lakes, rivers)",
        "roads": "Roads (main streets, paths)",
        "green": "Green spaces (parks, forests)",
        "buildings": "Buildings (houses, shops)",
        "landmarks": "Landmarks (churches, museums)",
        "recreation": "Recreation (marinas, beaches)",
        "food_drink": "Food & drink (restaurants, cafes)",
    }

    category_counts = {}
    for f in raw_features:
        ft = f["type"]
        if ft == "road":
            category_counts["roads"] = category_counts.get("roads", 0) + 1
        elif ft == "water":
            category_counts["water"] = category_counts.get("water", 0) + 1
        elif ft == "green":
            category_counts["green"] = category_counts.get("green", 0) + 1
        elif ft == "building":
            category_counts["buildings"] = category_counts.get("buildings", 0) + 1
        elif ft == "poi":
            tags = f.get("osm_tags", {})
            if any(tags.get(k) in ("restaurant", "cafe", "bar", "pub", "fast_food") for k in tags):
                category_counts["food_drink"] = category_counts.get("food_drink", 0) + 1
            elif any(tags.get(k) in ("marina", "beach_resort") for k in tags):
                category_counts["recreation"] = category_counts.get("recreation", 0) + 1
            else:
                category_counts["landmarks"] = category_counts.get("landmarks", 0) + 1

    categories = {k: (k in category_counts) for k in category_names}

    print("\nFeature categories to include:")
    cat_list = list(category_names.keys())
    for i, key in enumerate(cat_list, 1):
        check = "x" if categories[key] else " "
        count = category_counts.get(key, 0)
        print(f"  {i}. [{check}] {category_names[key]} ({count})")

    if _input_yes_no("Toggle categories?", default=False):
        toggle_input = input("  Toggle which? (comma-separated numbers): ").strip()
        try:
            indices = [int(x.strip()) for x in toggle_input.split(",")]
            for idx in indices:
                if 1 <= idx <= len(cat_list):
                    key = cat_list[idx - 1]
                    categories[key] = not categories[key]
        except ValueError:
            print("  Invalid input, keeping defaults.")

    config["categories"] = categories

    # Label style (v1: legend and none)
    print("\nLabel style:")
    print("  1) Labels + numbered legend")
    print("  2) No labels")
    label_choice = _input_int("Select [1-2]: ", 1, 2)
    config["label_style"] = {1: "legend", 2: "none"}[label_choice]

    # Border
    print("\nBorder style:")
    print("  1) Dotted border")
    print("  2) Double-line frame")
    print("  3) Dashed border")
    print("  4) None")
    border_choice = _input_int("Select border [1-4]: ", 1, 4)
    config["border_style"] = {1: "dotted", 2: "double_line", 3: "dashed", 4: None}[border_choice]

    # Colors
    print("\nColors:")
    config["colors"] = {}
    for key, default in DEFAULT_COLORS.items():
        config["colors"][key] = _input_with_default(key.replace("_", " ").title(), default)

    # Title
    name = candidate["name"].upper()
    location_parts = candidate["location_display"].split(", ")
    subtitle = location_parts[-1].upper() if location_parts else ""
    print(f"\nTitle: {name}")
    print(f"Subtitle: {subtitle}")
    if _input_yes_no("Edit title?", default=False):
        name = _input_with_default("Title", name)
        subtitle = _input_with_default("Subtitle", subtitle)
    config["title"] = name
    config["subtitle"] = subtitle

    return config


def step_generate_map(candidate, config, raw_features):
    """Process features and generate map SVG files."""
    processed = process_map_features(raw_features)

    all_coords = []
    for category in processed.values():
        for f in category:
            geom = f["geometry"]
            if hasattr(geom, "bounds"):
                minx, miny, maxx, maxy = geom.bounds
                all_coords.extend([(minx, miny), (maxx, maxy)])

    if not all_coords:
        print("  No features to render.")
        return False

    lons = [c[0] for c in all_coords]
    lats = [c[1] for c in all_coords]
    margin = 0.005
    bounds = (min(lons) - margin, min(lats) - margin, max(lons) + margin, max(lats) + margin)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_filename(candidate["name"], candidate["location_display"]) + "_map"

    editable_path = _unique_path(OUTPUT_DIR / f"{base_name}_editable.svg")
    cut_path = _unique_path(OUTPUT_DIR / f"{base_name}_cut.svg")

    print("\nGenerating map sticker...")

    editable_svg = generate_map_editable_svg(
        features=processed, bounds=bounds,
        title=config["title"], subtitle=config["subtitle"],
        colors=config.get("colors"), border_style=config["border_style"],
        label_style=config["label_style"],
    )
    cut_svg = generate_map_cut_svg(
        bounds=bounds, border_style=config["border_style"],
        colors=config.get("colors"),
    )

    editable_path.write_text(editable_svg)
    cut_path.write_text(cut_svg)

    print(f"  > {editable_path}  (layered, editable)")
    print(f"  > {cut_path}  (cut outline)")
    print(f"\nDone! Open the editable SVG in Inkscape/Illustrator for final touches.")
    return True


def run_map_flow():
    """Run the complete map sticker generation flow."""
    candidate = step_search_location()

    print("\nMap area:")
    for key, (label, _) in RADIUS_OPTIONS.items():
        print(f"  {key}) {label}")
    print("  4) Custom radius")
    area_choice = _input_int("Select [1-4]: ", 1, 4)

    if area_choice in RADIUS_OPTIONS:
        radius = RADIUS_OPTIONS[area_choice][1]
    else:
        custom = input("  Radius in meters [2000]: ").strip()
        try:
            radius = int(custom) if custom else 2000
        except ValueError:
            radius = 2000

    print(f"\nFetching map data for {candidate['name']} ({candidate['location_display']})...")
    try:
        raw_features = fetch_map_data(lat=candidate["lat"], lon=candidate["lon"], radius=radius)
    except RuntimeError as e:
        print(f"  Error: {e}")
        return

    type_counts = {}
    for f in raw_features:
        type_counts[f["type"]] = type_counts.get(f["type"], 0) + 1
    for ft, count in sorted(type_counts.items()):
        print(f"  {ft.title()}: {count}")

    if len(raw_features) < 5:
        print("  Warning: very few features found. Consider increasing the radius.")

    config = step_configure_map(candidate, raw_features)
    step_generate_map(candidate, config, raw_features)
