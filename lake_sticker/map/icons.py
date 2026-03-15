"""Icon library loader and OSM tag → icon mapping."""

import json
from pathlib import Path

_ICONS_DIR = Path(__file__).parent.parent / "icons"
_USER_ICONS_DIR = Path("user_icons")


def load_icon_mapping(user_dir=None):
    mapping = {}
    builtin_path = _ICONS_DIR / "mapping.json"
    if builtin_path.exists():
        mapping.update(json.loads(builtin_path.read_text()))
    if user_dir is None:
        user_dir = _USER_ICONS_DIR
    user_path = Path(user_dir) / "mapping.json"
    if user_path.exists():
        mapping.update(json.loads(user_path.read_text()))
    return mapping


def resolve_icon(osm_tags, mapping):
    for key, value in osm_tags.items():
        specific = f"{key}={value}"
        if specific in mapping:
            return mapping[specific]
    for key in osm_tags:
        wildcard = f"{key}=*"
        if wildcard in mapping:
            return mapping[wildcard]
    return "pin"


def load_icon_svg(icon_name, user_dir=None):
    if user_dir is None:
        user_dir = _USER_ICONS_DIR
    user_path = Path(user_dir) / f"{icon_name}.svg"
    if user_path.exists():
        return user_path.read_text()
    builtin_path = _ICONS_DIR / f"{icon_name}.svg"
    if builtin_path.exists():
        return builtin_path.read_text()
    raise FileNotFoundError(f"Icon '{icon_name}' not found")
