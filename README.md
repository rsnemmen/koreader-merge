# KOReader Highlights Merger

A utility script to merge KOReader notes/highlights files (sidecar `.lua` files from `.sdr` directories) from multiple devices.

---
**WARNING**  
⚠️Use this at your discretion and always make backups of your books and KOReader files/notes etc. This has been tested with EPUB and PDF books, and gave satisfactory results.

---

## Try it 

### Without installing

```bash
curl -fsSL https://raw.githubusercontent.com/rsnemmen/koreader-merge/main/merge_koreader.py \
  | python3 - file1.lua file2.lua -o output.lua
```

If you have [`uv`](https://github.com/astral-sh/uv), it can run the script directly from the URL:

```bash
uv run https://raw.githubusercontent.com/rsnemmen/koreader-merge/main/merge_koreader.py \
  -- file1.lua file2.lua -o output.lua
```

> **Note:** The optional `--render-html` / `--render-pdf` modes need `ebooklib` / `PyMuPDF`.
> These aren't pulled in by the one-liners above — for those features, use the permanent install below.

### Installation

```bash
curl -fsSL https://raw.githubusercontent.com/rsnemmen/koreader-merge/main/install.sh | bash
```

Installs `merge_koreader` to `/usr/local/bin` (or `~/.local/bin`). Requires Python 3.6+.

## Purpose

When reading the same book on multiple devices with KOReader, each device creates its own `metadata.*.lua` sidecar file containing highlights, bookmarks, and notes. This script merges those files into a single unified annotation file.

It ignores display settings, avoiding conflicts between devices with different screen sizes.

## Usage

```bash
merge_koreader.py <file1.lua> <file2.lua> [file3.lua ...] -o <output.lua>
```

Use `-v` for verbose output (shows duplicate count) or `-n` / `--dry-run` to preview without writing.

### Example

```bash
merge_koreader.py \
  ~/palma2/book.sdr/metadata.epub.lua \
  ~/go7/book.sdr/metadata.epub.lua \
  -o ~/synced/book.sdr/metadata.epub.lua
```

### Visualising annotations as HTML

Pass `--render-html` together with `--epub` to produce an HTML rendering of the epub with all annotations highlighted, colour-coded by source device:

```bash
merge_koreader.py \
  ~/palma2/book.sdr/metadata.epub.lua \
  ~/go7/book.sdr/metadata.epub.lua \
  -o merged.lua \
  --render-html --epub ~/books/mybook.epub
```

A colour legend at the top of the page maps each highlight colour to its source file. Annotations that carry a note show an inline `[note]` label (hover for the note text). Use `--html-output path/to/output.html` to set a custom output path (default: same name as the output `.lua` with a `.html` extension).

This feature requires one optional dependency:

```bash
pip install ebooklib
```

### Visualising annotations on PDF

Pass `--render-pdf` together with `--pdf` to overlay colour-coded highlights directly onto the PDF pages:

```bash
merge_koreader.py \
  ~/palma2/book.sdr/metadata.pdf.lua \
  ~/go7/book.sdr/metadata.pdf.lua \
  -o merged.lua \
  --render-pdf --pdf ~/books/mybook.pdf
```

Each source device gets a distinct highlight colour. Notes are attached as popup annotations (visible on hover in most PDF readers). A legend page is inserted at the start of the document mapping each colour to its source file. Use `--pdf-output path/to/output.pdf` to set a custom output path (default: same name as the output `.lua` with a `.pdf` extension).

This feature requires one optional dependency:

```bash
pip install PyMuPDF
```

## Behavior

- **Merged**: Highlights, bookmarks, notes, and reading progress
- **Deduplicated**: Identical annotations are not duplicated
- **Not preserved**: Display settings (font size, margins, line spacing, etc.)

When opening a book with the merged file, KOReader applies settings in this order: 1. Per-book sidecar settings → 2. Directory defaults → 3. Global defaults

Since display settings are not merged, KOReader will fall back to your configured defaults.

## Requirements

- Python 3.6+
- No external dependencies for the core merge workflow
- `ebooklib` is required only for `--render-html`
- `PyMuPDF` is required only for `--render-pdf`
