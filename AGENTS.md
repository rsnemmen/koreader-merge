# Agent Instructions for koreader_merge_highlights

## Project Overview
Single-file Python utility (654 lines) that merges KOReader annotation files from multiple devices. No external dependencies, standard library only.

## Commands

### Running the Script
```bash
# Merge multiple Lua files
python merge_koreader.py file1.lua file2.lua -o output.lua

# With verbose output
python merge_koreader.py file1.lua file2.lua -o output.lua -v

# Dry run (preview without writing)
python merge_koreader.py file1.lua file2.lua -o output.lua -n
```

### Code Quality
```bash
# Manual syntax check
python -m py_compile merge_koreader.py

# Type check (if mypy available)
mypy merge_koreader.py --ignore-missing-imports

# Lint (if ruff available)
ruff check merge_koreader.py

# Format (if ruff available)
ruff format merge_koreader.py
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

# No external dependencies allowed
```

### Naming Conventions
- Functions: `snake_case` (e.g., `parse_lua_table`, `merge_annotations`)
- Variables: `snake_case` (e.g., `annotations_list`, `merged_annotations`)
- Constants: `UPPER_SNAKE_CASE` (if any)
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
This project has no formal test suite. When making changes:
1. Test with actual KOReader Lua files
2. Verify output is valid Lua syntax
3. Test with both EPUB and PDF annotation files
4. Ensure merged files load correctly in KOReader

## Architecture

### Key Functions
- `parse_lua_file()` - Entry point for parsing KOReader metadata files
- `parse_lua_table()` - Recursive Lua table parser
- `parse_lua_value()` - Dispatch to appropriate value parser
- `merge_annotations()` - Deduplicate and merge annotation lists
- `format_lua_value()` - Serialize Python data back to Lua
- `generate_lua_output()` - Build final Lua file content

### Data Flow
1. Read Lua file → parse into Python dict
2. Extract annotations from all input files
3. Merge and deduplicate annotations
4. Build output data structure (no display settings)
5. Serialize to Lua format and write

## Important Notes
- **No display settings merged** - only annotations, bookmarks, notes, and reading progress
- **Deduplication** uses annotation position/page as key
- **Sort order** is deterministic (stable across runs)
- **Backwards compatibility** with Python 3.6 required
- Keep script standalone - no external dependencies
