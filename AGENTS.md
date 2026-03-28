# Agent Instructions for koreader_merge_highlights

## Project Overview
Single-file Python utility (~1030 lines) that merges KOReader annotation files from multiple devices. Standard library only for the core merge workflow; `ebooklib` and `PyMuPDF` are optional dependencies for rendering. Uses `python3.13` (conda).

## Commands

### Running the Script
```bash
# Merge multiple Lua files
python3.13 merge_koreader.py file1.lua file2.lua -o output.lua

# With verbose output
python3.13 merge_koreader.py file1.lua file2.lua -o output.lua -v

# Dry run (preview without writing)
python3.13 merge_koreader.py file1.lua file2.lua -o output.lua -n

# Render epub with colour-coded highlights to HTML (requires ebooklib)
python3.13 merge_koreader.py file1.lua file2.lua -o output.lua --epub mybook.epub --html-output out.html

# Overlay colour-coded highlights on a PDF (requires PyMuPDF)
python3.13 merge_koreader.py file1.lua file2.lua -o output.lua --pdf mybook.pdf --pdf-output out.pdf
```

### Code Quality
```bash
# Syntax check
python3.13 -m py_compile merge_koreader.py

# Type check (if mypy available)
mypy merge_koreader.py --ignore-missing-imports

# Lint (if ruff available)
ruff check merge_koreader.py

# Format (if ruff available)
ruff format merge_koreader.py

# Run tests
python3.13 -m pytest tests/
```

## Code Style Guidelines

### Python Standards
- Python 3.6+ compatible (avoid 3.7+ features like dataclasses)
- Type hints required for all function parameters and return values
- Docstrings for all functions (Google style)
- Maximum line length: 100 characters

### Imports
```python
# Standard library imports first
import argparse
import re
import sys
from typing import Any, Dict, List, Tuple

# Optional dependencies imported lazily inside functions (never at top level)
# ebooklib — only in render_annotated_html()
# fitz (PyMuPDF) — only in render_annotated_pdf()
```

### Naming Conventions
- Functions: `snake_case` (e.g., `parse_lua_table`, `merge_annotations`)
- Variables: `snake_case` (e.g., `annotations_list`, `merged_annotations`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEVICE_COLORS`)
- Type variables: follow PEP 8

### Formatting
- Indentation: 4 spaces (no tabs)
- Quotes: Prefer double quotes for strings
- Trailing commas in multi-line structures
- Two blank lines between top-level functions
- One blank line between methods in a class

### Types
- Use `typing` module imports: `Any`, `Dict`, `List`, `Tuple`
- Avoid `Optional[]` - use `Union[X, None]` or `X | None` (if 3.10+)
- Use precise types when possible (e.g., `List[Dict]` not just `List`)

### Error Handling
- Raise `ValueError` for parsing errors with descriptive messages
- Use `try/except` blocks for file operations
- Print errors to `sys.stderr` and exit with code 1 for CLI errors
- Handle edge cases gracefully (e.g., missing keys, type conversions)

### Function Design
- Keep functions focused and single-purpose
- Parse functions return `(value, new_position)` tuple pattern
- Helper functions should be pure when possible
- Document complex logic with inline comments

### Lua Parsing Specifics
- Handle both string key syntax: `["key"]` and identifier keys
- Support Lua long strings: `[[...]]` and `[=[...]=]`
- Properly escape special characters when serializing
- Sort dictionary keys for deterministic output (integers first, then strings)

### Testing Approach
Tests live in `tests/test_merge.py`. Run with `python3.13 -m pytest tests/`. Fixtures are in `tests/fixtures/`:
- `device_a.lua`, `device_b.lua` — synthetic fixtures
- `arabia_deserta_palma2.pdf.lua`, `arabia_deserta_go7.pdf.lua` — real PDF annotation fixtures
- `arabia_deserta.pdf` — source PDF for render tests
- `palo_alto_palma2.epub.lua`, `palo_alto_go7.epub.lua` — real epub annotation fixtures
- `palo_alto.epub` — source epub for render tests

## Architecture

### Key Functions
- `parse_lua_file()` — Entry point for parsing KOReader metadata files
- `parse_lua_table()` — Recursive Lua table parser
- `parse_lua_value()` — Dispatch to appropriate value parser
- `merge_annotations()` — Deduplicate and merge annotation lists
- `annotation_key()` — Generates deduplication key (pos0/pos1 for highlights, page/chapter for bookmarks)
- `format_lua_value()` — Serialize Python data back to Lua
- `generate_lua_output()` — Build final Lua file content
- `render_annotated_html()` — Render epub with colour-coded highlights to HTML (requires ebooklib)
- `render_annotated_pdf()` — Overlay colour-coded highlights on a PDF (requires PyMuPDF)
- `_hex_to_rgb()` — Convert `#RRGGBB` to float RGB tuple for PyMuPDF

### Data Flow
1. Read Lua file → parse into Python dict
2. Extract annotations from all input files
3. Tag each annotation with `_device_index` for colour-coding
4. Merge and deduplicate annotations
5. Build output data structure (no display settings)
6. Serialize to Lua format and write
7. Optionally render HTML (epub) or annotated PDF

## Important Notes
- **No display settings merged** — only annotations, bookmarks, notes, and reading progress
- **Deduplication** uses annotation position/page as key
- **Sort order** is deterministic (stable across runs)
- **`_device_index`** keys are stripped from Lua output (keys starting with `_` are filtered)
- **pboxes** in PDF annotations are parsed as `{1: {...}, 2: {...}}` dicts by the Lua parser, not lists
- **Coordinate system**: KOReader pboxes use top-left origin matching PyMuPDF — no transform needed
