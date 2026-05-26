# Sticker Maker

## Knowledge Base (REQUIRED)

This project is part of the Lakeshore Studio workspace. A shared knowledge base lives at
`/home/justin/lakeshore-studio/knowledge-base/projects/sticker-maker/`.

**On every session where commits are made, you MUST:**
1. Write a session note to `sessions/` using the template at
   `/home/justin/lakeshore-studio/knowledge-base/templates/session.md`
2. Update `_index.md` Recent Sessions to reference today's session note

The Stop hook will verify these exist. Do not end a session with unresolved KB checks.

## Overview

Generate lake sticker SVGs from OpenStreetMap data.

## Commands

```bash
# Install
pip install -e .

# Install with osmnx extras
pip install -e ".[osmnx]"

# Install dev dependencies
pip install -e ".[dev]"

# Run CLI
lake-sticker

# Generate the New Hampshire base map + township stickers
#   (install the townships extra first: pip install -e ".[townships]")
nh-map --out-dir output/nh

# Run tests
pytest
```
