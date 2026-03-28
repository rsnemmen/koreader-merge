# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Single-file Python utility (`merge_koreader.py`) that merges KOReader annotation files (`.lua`) from multiple devices into one. Standard library only for the core merge workflow; `ebooklib` and `weasyprint` are optional dependencies used only when `--render-pdf` is passed. Python 3.6+ compatible.

## Commands

```bash
# Merge multiple Lua files
python merge_koreader.py file1.lua file2.lua -o output.lua

# With verbose output
python merge_koreader.py file1.lua file2.lua -o output.lua -v

# Render epub with colour-coded annotation highlights to PDF (requires ebooklib + weasyprint)
python merge_koreader.py file1.lua file2.lua -o output.lua --render-pdf --epub mybook.epub
python merge_koreader.py file1.lua file2.lua -o output.lua --render-pdf --epub mybook.epub --pdf-output annotations.pdf

# Syntax check
python -m py_compile merge_koreader.py

# Type check
mypy merge_koreader.py --ignore-missing-imports

# Lint / format
ruff check merge_koreader.py
ruff format merge_koreader.py
```

## Architecture & Data Flow

All logic lives in `merge_koreader.py` (single file, ~850 lines):

1. **Parse** — `parse_lua_file()` → `parse_lua_table()` → `parse_lua_value()`: Hand-written recursive Lua parser. Parse functions follow a `(value, new_position)` return tuple pattern.
2. **Merge** — `merge_annotations()`: Deduplicates using position/page as key (`annotation_key()`), keeps most recent version by `datetime_updated`. Sorted via `annotation_sort_key()` for deterministic output.
3. **Serialize** — `format_lua_value()` → `generate_lua_output()`: Converts Python dicts back to Lua syntax. Dict keys are sorted (integers first, then strings alphabetically).

**What is merged:** annotations, bookmarks, notes, reading progress, metadata (`doc_props`, `doc_pages`, `doc_path`).

**What is intentionally excluded:** display settings (font size, margins, line spacing) — KOReader falls back to per-device defaults when these are absent.

## Code Style

- Type hints required for all functions; use `typing` module (`Any`, `Dict`, `List`, `Tuple`)
- Google-style docstrings on all functions
- Max line length: 100 characters
- Double quotes for strings
- No external dependencies for the core merge path — keep it stdlib-only
- Optional PDF rendering (`render_annotated_pdf`, `_highlight_text_in_html`) may import `ebooklib` and `weasyprint` lazily at runtime
