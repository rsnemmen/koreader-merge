# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Single-file Python utility (`merge_koreader.py`) that merges KOReader annotation files (`.lua`) from multiple devices into one. Standard library only for the core merge workflow; `ebooklib` is optional for `--render-html` and `PyMuPDF` is optional for `--render-pdf`. Uses `python3.13` (conda). Python 3.6+ compatible.

## Commands

```bash
# Merge multiple Lua files
python3.13 merge_koreader.py file1.lua file2.lua -o output.lua

# With verbose output
python3.13 merge_koreader.py file1.lua file2.lua -o output.lua -v

# Render epub with colour-coded annotation highlights to HTML (requires ebooklib)
python3.13 merge_koreader.py file1.lua file2.lua -o output.lua --render-html --epub mybook.epub
python3.13 merge_koreader.py file1.lua file2.lua -o output.lua --epub mybook.epub --html-output annotations.html

# Overlay colour-coded highlights on a PDF (requires PyMuPDF: pip install PyMuPDF)
python3.13 merge_koreader.py file1.lua file2.lua -o output.lua --render-pdf --pdf mybook.pdf
python3.13 merge_koreader.py file1.lua file2.lua -o output.lua --pdf mybook.pdf --pdf-output annotated.pdf

# Syntax check
python3.13 -m py_compile merge_koreader.py

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
- Optional rendering functions import lazily: `render_annotated_html` imports `ebooklib`; `render_annotated_pdf` imports `fitz` (PyMuPDF)
