
## Appendix

### What the script does in more details

**Parsing**: Implements a complete Lua table parser that handles strings (with escape sequences and line continuations), numbers, booleans, nil, and nested tables.

**Deduplication**: Identifies duplicate annotations by comparing position data (`pos0`/`pos1` for highlights) or page location (for bookmarks). When duplicates exist, it keeps the most recently modified version.

**Merging**: Combines all unique annotations and sorts them by page number and position.

**Output**: Generates a clean Lua file containing only annotations plus essential document metadata (`doc_props`, `doc_pages`, `stats`, `summary`)—no display settings like font size, margins, or rendering options.

**Stats**: Recalculates highlight and note counts based on the merged data.

### The original prompt

write a python script that takes as input (command-line arguments) the LUA files for the same book, written by different KOReader apps in different devices. 

the script should combine the notes and highlights from the different files, and produce a LUA file with the joint notes and annotations. it should not include display settings in this output.

### What is KOReader's behavior when it opens a book and its LUA file does not have display settings?

Based on the search results, when KOReader opens a book and its sidecar (metadata.lua) file is missing display settings, it uses a fallback system:

KOReader extends DocSettings to allow per directory defaults for book settings. If the file does not have a sidecar it recursively looks for a directory default to put as the settings. It stops on the first parent directory it finds defaults for (children override parents).[[7]](https://github.com/koreader/koreader/pull/5428)

For users who wish to edit config files directly, there are two such files that contain the initial settings for KOReader's behavior and appearance: The `defaults.lua` located at `koreader/defaults.lua`, and the `cr3.ini` located at `koreader/data/cr3.ini`, especially for EPUB/FB2 documents.[[3]](https://github.com/koreader/koreader/wiki/Change-defaults)

So the behavior is:

1. **Per-book sidecar settings** are checked first (your `metadata.lua` file)
2. If a setting is missing, KOReader falls back to **directory defaults** (if configured)
3. Finally, it falls back to the **global defaults** from `defaults.lua` (or `defaults.custom.lua`)

This means the script I provided is safe to use — when you open a book with the merged annotations file that lacks display settings, KOReader will simply apply your global default settings (font size, margins, line spacing, etc.) as if you were opening the book for the first time.

**The practical effect**: Your annotations and highlights will be preserved, but the book will open with your device's default display preferences rather than the per-book customizations you may have made. If you had customized the font size or margins specifically for that book on one device, you'd need to re-adjust them.

Would you like me to modify the script to optionally preserve display settings from one of the source files (e.g., the most recently modified one)?