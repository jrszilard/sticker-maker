"""Interactive CLI for the Lake Sticker Maker."""

from pathlib import Path

from lake_sticker.search import search_lakes, sanitize_filename, SearchError
from lake_sticker.geometry import fetch_geometry, process_geometry, auto_tolerance, tolerance_to_meters, GeometryError
from lake_sticker.svg import generate_editable_svg, generate_cut_svg

OUTPUT_DIR = Path("output")

# Defaults
DEFAULT_FILL = "#1a3a5c"
DEFAULT_TOLERANCE = None  # auto


def _input_with_default(prompt, default):
    """Prompt for input with a default value shown in brackets."""
    raw = input(f"  {prompt} [{default}]: ").strip()
    return raw if raw else default


def _input_int(prompt, min_val, max_val):
    """Prompt for an integer in a range, re-prompting on invalid input."""
    while True:
        raw = input(prompt).strip()
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
            print(f"  Please enter a number between {min_val} and {max_val}.")
        except ValueError:
            print(f"  Please enter a number between {min_val} and {max_val}.")


def _input_yes_no(prompt, default=False):
    """Prompt for y/n with a default."""
    suffix = "[y/N]" if not default else "[Y/n]"
    raw = input(f"{prompt} {suffix}: ").strip().lower()
    if not raw:
        return default
    return raw.startswith("y")


def _unique_path(base_path):
    """Return base_path if it doesn't exist, else append _2, _3, etc."""
    if not base_path.exists():
        return base_path
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _step_search():
    """Search for a lake and return the selected candidate."""
    while True:
        query = input("\nEnter lake name: ").strip()
        if not query:
            continue

        print("\nSearching OpenStreetMap...")
        try:
            candidates = search_lakes(query)
        except SearchError as e:
            print(f"  Error: {e}")
            continue

        if not candidates:
            print("  No lakes found. Try a different name or add a state (e.g., 'Crystal Lake, NH').")
            continue

        if len(candidates) == 1:
            c = candidates[0]
            print(f"  Found: {c['name']} -- {c['location_display']}")
            if _input_yes_no("  Use this?", default=True):
                return c
            continue

        # Show numbered list
        display_count = min(len(candidates), 15)
        print(f"Found {len(candidates)} results:\n")
        for i, c in enumerate(candidates[:display_count], 1):
            print(f"  {i}) {c['name']} -- {c['location_display']}")
        if len(candidates) > 15:
            print(f"\n  (Showing 15 of {len(candidates)}. Add a state to narrow results.)")

        idx = _input_int(f"\nSelect a lake [1-{display_count}]: ", 1, display_count)
        return candidates[idx - 1]


def _step_configure(candidate):
    """Configure label, border, colors, and simplification."""
    config = {}

    # Auto-detect label from lake name
    name = candidate["name"].upper()
    # Extract state from location_display
    location_parts = candidate["location_display"].split(", ")
    subtitle = location_parts[-1].upper() if location_parts else ""

    print(f"\nLabel: {name}")
    print(f"Subtitle: {subtitle}")
    if _input_yes_no("Edit label?", default=False):
        name = _input_with_default("Label", name)
        subtitle = _input_with_default("Subtitle", subtitle)

    config["label"] = name
    config["subtitle"] = subtitle

    # Border style
    print("\nBorder style:")
    print("  1) Dotted ring")
    print("  2) Double-line frame")
    print("  3) Dashed ring")
    print("  4) None")
    border_choice = _input_int("Select border [1-4]: ", 1, 4)
    border_map = {1: "dotted", 2: "double_line", 3: "dashed", 4: None}
    config["border_style"] = border_map[border_choice]

    # Simplification tolerance
    print("\nSimplification (higher = smoother for vinyl):")
    print(f"  Auto-calculated value will be shown after geometry fetch.")
    print(f"  [Enter to keep auto, or type a value like 0.0003]")
    tol_input = input("  Tolerance [auto]: ").strip()
    if tol_input:
        try:
            config["tolerance"] = float(tol_input)
        except ValueError:
            print("  Invalid value, using auto.")
            config["tolerance"] = None
    else:
        config["tolerance"] = None

    # Colors
    print("\nColors:")
    config["fill_color"] = _input_with_default("Fill", DEFAULT_FILL)
    config["label_color"] = _input_with_default("Label", config["fill_color"])

    return config


def _step_generate(candidate, config):
    """Fetch geometry and generate SVG files."""
    print(f"\nFetching geometry for {candidate['name']} ({candidate['location_display']})...")

    try:
        geom = fetch_geometry(
            osm_id=candidate["osm_id"],
            osm_type=candidate["osm_type"],
        )
    except GeometryError as e:
        print(f"  Error: {e}")
        return False

    # Process geometry
    ext_coords, island_coords = process_geometry(geom, tolerance=config["tolerance"])
    print(f"  Shoreline: {len(ext_coords)} points")
    print(f"  Islands: {len(island_coords)}")

    # Generate SVGs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_filename(candidate["name"], candidate["location_display"])

    editable_path = _unique_path(OUTPUT_DIR / f"{base_name}_editable.svg")
    cut_path = _unique_path(OUTPUT_DIR / f"{base_name}_cut.svg")

    editable_svg = generate_editable_svg(
        ext_coords=ext_coords,
        island_coords=island_coords,
        label=config["label"],
        subtitle=config["subtitle"],
        fill_color=config["fill_color"],
        border_style=config["border_style"],
        label_color=config["label_color"],
    )
    cut_svg = generate_cut_svg(
        ext_coords=ext_coords,
        island_coords=island_coords,
        fill_color=config["fill_color"],
        border_style=config["border_style"],
    )

    editable_path.write_text(editable_svg)
    cut_path.write_text(cut_svg)

    print(f"\n  > {editable_path}  (separate layers)")
    print(f"  > {cut_path}  (single path, vinyl-ready)")
    print(f"\nDone! Open the editable SVG in Inkscape/Illustrator for final touches.")
    return True


def main():
    """Main entry point for the Lake Sticker Maker CLI."""
    print("\nLake Sticker Maker")
    print("=" * 22)

    while True:
        print("\nWhat would you like to create?")
        print("  1) Lake sticker")
        print("  2) Map sticker")
        mode = _input_int("Select [1-2]: ", 1, 2)

        if mode == 1:
            candidate = _step_search()
            config = _step_configure(candidate)
            _step_generate(candidate, config)
        else:
            from lake_sticker.map.cli import run_map_flow
            run_map_flow()

        if not _input_yes_no("\nGenerate another?", default=False):
            break

    print("\nGoodbye!")
