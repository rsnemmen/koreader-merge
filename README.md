# KOReader Highlights Merger

A utility script to merge KOReader notes/highlights files (sidecar `.lua` files from `.sdr` directories) from multiple devices.

---
**WARNING**  
⚠️Use this at your discretion and always make backups of your books and KOReader files/notes etc. This has been tested with EPUB and PDF books, and gave satisfactory results (see Tests below).

---

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

## Tests

- [x] ePub book with notes from Palma 2 and Go 7 color. BlueStacks emulator. Preserves highlights colors and notes. 
- [x] PDF book with notes from Palma 2 and Go 7 color. BlueStacks emulator.  Preserves highlights colors and notes. 


## TODO  

Additional testing welcome—particularly across different e-reader devices and book formats.

- [ ] test on actual devices
- [x] test
	- [x] diff original files with output
	- [x] test output in one of the devices
	- [x] test in android simulator
- [x] test PDF book
- [x] release on github


## Disclaimers

This project would benefit from additional community testing, particularly on physical e-reader devices. Please keep backups of your book annotations. 

