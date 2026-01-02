# KOReader Highlights Merger

A utility script to merge KOReader notes/highlights files (sidecar `.lua` files from `.sdr` directories) from multiple devices.

---
**WARNING**  
⚠️Use this at your discretion and always make backups of your books and KOReader files/notes etc.

---

## Purpose

When reading the same book on multiple devices with KOReader, each device creates its own `metadata.*.lua` sidecar file containing highlights, bookmarks, and notes. This script merges those files into a single unified annotation file.

It ignores display settings, avoiding conflicts between devices with different screen sizes.

## Usage

```bash
koreader_merge.py <file1.lua> <file2.lua> [file3.lua ...] -o <output.lua>
```

### Example

```bash
koreader_merge.py \
  ~/palma2/book.sdr/metadata.epub.lua \
  ~/go7/book.sdr/metadata.epub.lua \
  -o ~/synced/book.sdr/metadata.epub.lua
```

## Behavior

- **Merged**: Highlights, bookmarks, notes, and reading progress
- **Deduplicated**: Identical annotations are not duplicated
- **Not preserved**: Display settings (font size, margins, line spacing, etc.)

When opening a book with the merged file, KOReader applies settings in this order: 1. Per-book sidecar settings → 2. Directory defaults → 3. Global defaults

Since display settings are not merged, KOReader will fall back to your configured defaults.

## Requirements

- Python 3.6+
- No external dependencies

## Tests

- [x] ePub book with notes from Palma 2 and Go 7 color. Preserves highlights colors and notes. 
- [ ] PDF book


## TODO  

I need more testers.

- [x] test
	- [x] diff original files with output
	- [x] test output in one of the devices
	- [x] test in android simulator
- [ ] test PDF book
- [x] release on github
- [ ] homebrew


## Disclaimers

This is a vibe-coded script generated with Claude Opus 4.5. Proceed carefully. 

