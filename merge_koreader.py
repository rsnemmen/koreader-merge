#!/usr/bin/env python
"""
Merge KOReader annotations from multiple devices.

Usage: python merge_koreader.py file1.lua file2.lua [file3.lua ...] -o output.lua
"""

import argparse
import html as html_module
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# Highlight colors for annotations, one per source device (cycles if more than 5)
DEVICE_COLORS = ["#FFFF99", "#99FFFF", "#FF99CC", "#99FF99", "#FFD699"]


def _hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    """Convert '#RRGGBB' hex color to (r, g, b) floats in [0, 1] for PyMuPDF."""
    h = hex_color.lstrip('#')
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def parse_lua_string(s: str, pos: int) -> Tuple[str, int]:
    """Parse a Lua string literal."""
    quote_char = s[pos]
    pos += 1
    result = []
    
    while pos < len(s):
        if s[pos] == '\\':
            pos += 1
            if pos >= len(s):
                break
            escape_char = s[pos]
            if escape_char == 'n':
                result.append('\n')
            elif escape_char == 't':
                result.append('\t')
            elif escape_char == 'r':
                result.append('\r')
            elif escape_char == '\\':
                result.append('\\')
            elif escape_char == '"':
                result.append('"')
            elif escape_char == "'":
                result.append("'")
            elif escape_char == '\n':
                # Line continuation - skip the newline
                result.append('\n')
            elif escape_char == '\r':
                # Handle \r\n line endings
                if pos + 1 < len(s) and s[pos + 1] == '\n':
                    pos += 1
                result.append('\n')
            elif escape_char == 'a':
                result.append('\x07')
            elif escape_char == 'b':
                result.append('\x08')
            elif escape_char == 'f':
                result.append('\x0c')
            elif escape_char == 'v':
                result.append('\x0b')
            elif escape_char == 'x':
                # Hex escape \xhh
                hex_str = s[pos + 1:pos + 3]
                if len(hex_str) == 2 and all(c in '0123456789abcdefABCDEF' for c in hex_str):
                    result.append(chr(int(hex_str, 16)))
                    pos += 2
                else:
                    # Invalid hex escape: emit literally (backslash + 'x')
                    result.append('\\')
                    result.append(escape_char)
            elif escape_char.isdigit():
                # Decimal escape \ddd (1-3 digits)
                dec_str = escape_char
                if pos + 1 < len(s) and s[pos + 1].isdigit():
                    dec_str += s[pos + 1]
                    pos += 1
                    if pos + 1 < len(s) and s[pos + 1].isdigit():
                        dec_str += s[pos + 1]
                        pos += 1
                result.append(chr(int(dec_str)))
            else:
                result.append(escape_char)
            pos += 1
        elif s[pos] == quote_char:
            pos += 1
            break
        else:
            result.append(s[pos])
            pos += 1
    
    return ''.join(result), pos


def parse_lua_long_string(s: str, pos: int) -> Tuple[str, int]:
    """Parse a Lua long string [[...]] or [=[...]=] etc."""
    # Count the equals signs
    eq_start = pos + 1
    eq_count = 0
    while eq_start + eq_count < len(s) and s[eq_start + eq_count] == '=':
        eq_count += 1
    
    # Find the opening bracket
    open_bracket = eq_start + eq_count
    if open_bracket >= len(s) or s[open_bracket] != '[':
        raise ValueError(f"Invalid long string at position {pos}")
    
    pos = open_bracket + 1
    
    # Build the closing pattern
    close_pattern = ']' + ('=' * eq_count) + ']'
    
    # Find the closing pattern
    end_pos = s.find(close_pattern, pos)
    if end_pos == -1:
        raise ValueError(f"Unterminated long string starting at position {pos}")
    
    content = s[pos:end_pos]
    # Remove leading newline if present
    if content.startswith('\n'):
        content = content[1:]
    
    return content, end_pos + len(close_pattern)


def skip_whitespace_and_comments(s: str, pos: int) -> int:
    """Skip whitespace and Lua comments."""
    while pos < len(s):
        # Skip whitespace
        if s[pos] in ' \t\n\r':
            pos += 1
            continue
        
        # Skip single-line comments
        if pos < len(s) - 1 and s[pos:pos+2] == '--':
            # Check for long comment --[[...]]
            if pos < len(s) - 3 and s[pos+2] == '[' and s[pos+3] in '[=':
                # Find end of long comment
                bracket_pos = pos + 2
                eq_count = 0
                while bracket_pos + 1 + eq_count < len(s) and s[bracket_pos + 1 + eq_count] == '=':
                    eq_count += 1
                if bracket_pos + 1 + eq_count < len(s) and s[bracket_pos + 1 + eq_count] == '[':
                    close_pattern = ']' + ('=' * eq_count) + ']'
                    end_pos = s.find(close_pattern, bracket_pos + 2 + eq_count)
                    if end_pos != -1:
                        pos = end_pos + len(close_pattern)
                        continue
            
            # Single-line comment
            while pos < len(s) and s[pos] != '\n':
                pos += 1
            continue
        
        break
    
    return pos


def parse_lua_value(s: str, pos: int) -> Tuple[Any, int]:
    """Parse a Lua value (string, number, boolean, table, nil)."""
    pos = skip_whitespace_and_comments(s, pos)
    
    if pos >= len(s):
        raise ValueError("Unexpected end of input")
    
    # Long string
    if s[pos] == '[' and pos + 1 < len(s) and s[pos + 1] in '[=':
        return parse_lua_long_string(s, pos)
    
    # Regular string
    if s[pos] in '"\'':
        return parse_lua_string(s, pos)
    
    # Table
    if s[pos] == '{':
        return parse_lua_table(s, pos)
    
    # Boolean or nil
    if s[pos:pos+4] == 'true' and (pos + 4 >= len(s) or not (s[pos+4].isalnum() or s[pos+4] == '_')):
        return True, pos + 4
    if s[pos:pos+5] == 'false' and (pos + 5 >= len(s) or not (s[pos+5].isalnum() or s[pos+5] == '_')):
        return False, pos + 5
    if s[pos:pos+3] == 'nil' and (pos + 3 >= len(s) or not (s[pos+3].isalnum() or s[pos+3] == '_')):
        return None, pos + 3
    
    # Number (including negative and scientific notation)
    match = re.match(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', s[pos:])
    if match:
        num_str = match.group()
        if '.' in num_str or 'e' in num_str.lower():
            return float(num_str), pos + len(num_str)
        else:
            return int(num_str), pos + len(num_str)
    
    raise ValueError(f"Unexpected character at position {pos}: '{s[pos:pos+20]}'")


def parse_lua_table(s: str, pos: int) -> Tuple[Dict, int]:
    """Parse a Lua table."""
    if s[pos] != '{':
        raise ValueError(f"Expected '{{' at position {pos}")
    pos += 1
    
    result = {}
    
    while True:
        pos = skip_whitespace_and_comments(s, pos)
        
        if pos >= len(s):
            raise ValueError("Unterminated table")
        
        if s[pos] == '}':
            pos += 1
            break
        
        if s[pos] == ',':
            pos += 1
            continue
        
        # Parse key
        if s[pos] == '[':
            pos += 1
            pos = skip_whitespace_and_comments(s, pos)
            
            key: Any
            if s[pos] in '"\'':
                key, pos = parse_lua_string(s, pos)
            else:
                # Numeric key
                match = re.match(r'-?\d+', s[pos:])
                if match:
                    key = int(match.group())
                    pos += len(match.group())
                else:
                    raise ValueError(f"Invalid key at position {pos}")
            
            pos = skip_whitespace_and_comments(s, pos)
            
            if s[pos] != ']':
                raise ValueError(f"Expected ']' at position {pos}")
            pos += 1
        else:
            # Identifier key
            match = re.match(r'[a-zA-Z_][a-zA-Z0-9_]*', s[pos:])
            if match:
                key = match.group()
                pos += len(match.group())
            else:
                raise ValueError(f"Invalid key at position {pos}: '{s[pos:pos+20]}'")
        
        pos = skip_whitespace_and_comments(s, pos)
        
        if s[pos] != '=':
            raise ValueError(f"Expected '=' at position {pos}")
        pos += 1
        
        value, pos = parse_lua_value(s, pos)
        result[key] = value
        
        pos = skip_whitespace_and_comments(s, pos)
        
        if pos < len(s) and s[pos] == ',':
            pos += 1
    
    return result, pos


def parse_lua_file(filepath: str) -> Dict:
    """Parse a KOReader Lua metadata file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    match = re.search(r'return\s*\{', content)
    if not match:
        raise ValueError(f"No 'return {{' found in {filepath}")
    
    pos = match.end() - 1
    result, _ = parse_lua_table(content, pos)
    return result


def freeze_for_key(x: Any) -> Any:
    """
    Convert potentially unhashable nested structures (dict/list)
    into hashable equivalents for use in dict/set keys.
    """
    if isinstance(x, dict):
        # Sort items to ensure stable ordering
        return tuple((freeze_for_key(k), freeze_for_key(v)) for k, v in sorted(x.items(), key=lambda kv: str(kv[0])))
    if isinstance(x, list):
        return tuple(freeze_for_key(v) for v in x)
    if isinstance(x, tuple):
        return tuple(freeze_for_key(v) for v in x)
    # ints, floats, strs, bools, None are hashable already
    return x


def annotation_sort_key(ann: Dict) -> Tuple[int, int, int, float, float, str]:
    """
    Total ordering for annotations that is stable across different schemas.

    Always returns:
      (kind_rank, pageno, pos_page, y, x, datetime)

    No mixed int/str comparisons.
    """
    # Prefer pageno; fall back to page; then 0
    pageno_raw = ann.get("pageno", ann.get("page", 0))
    try:
        pageno = int(pageno_raw) if pageno_raw is not None else 0
    except (TypeError, ValueError):
        pageno = 0

    # Determine kind:
    # - PDF highlight-like annotations have pos0/pos1
    # - "chapter marker" entries in your files have text like "in CHAPTER ..."
    has_pos = "pos0" in ann and "pos1" in ann
    is_chapter_marker = (
        isinstance(ann.get("text"), str)
        and ann["text"].startswith("in ")
        and not has_pos
    )

    # Put real highlights first, then bookmarks/others, then chapter markers (or vice versa if you prefer)
    if has_pos:
        kind_rank = 0
    elif is_chapter_marker:
        kind_rank = 2
    else:
        kind_rank = 1

    pos0 = ann.get("pos0")

    # Defaults for missing/unknown position
    pos_page = pageno
    y = 0.0
    x = 0.0

    if isinstance(pos0, dict):
        # PDF style
        try:
            pos_page = int(pos0.get("page", pageno) or pageno)
        except (TypeError, ValueError):
            pos_page = pageno

        try:
            y = float(pos0.get("y", 0.0) or 0.0)
        except (TypeError, ValueError):
            y = 0.0

        try:
            x = float(pos0.get("x", 0.0) or 0.0)
        except (TypeError, ValueError):
            x = 0.0

    # Datetime as final tie-breaker; always string
    dt = ann.get("datetime_updated", ann.get("datetime", ""))
    if dt is None:
        dt = ""
    else:
        dt = str(dt)

    return (kind_rank, pageno, pos_page, y, x, dt)


def annotation_key(ann: Dict) -> Tuple:
    """Generate a unique key for an annotation to detect duplicates."""
    # For highlights with position data
    if 'pos0' in ann and 'pos1' in ann:
        return ('highlight', freeze_for_key(ann.get('pos0')), freeze_for_key(ann.get('pos1')))
    # For bookmarks without position data, use page location
    page = ann.get('page') or ann.get('pageno')
    return ('bookmark', freeze_for_key(page), freeze_for_key(ann.get('chapter')))


def merge_annotations(annotations_list: List[List[Dict]]) -> Tuple[List[Dict], int]:
    """Merge annotations from multiple sources, keeping the most recent version.

    Returns:
        A tuple of (merged annotation list, number of duplicates removed).
    """
    merged: Dict[Any, Dict] = {}
    total_input = 0

    for annotations in annotations_list:
        for ann in annotations:
            total_input += 1
            key = annotation_key(ann)

            if key in merged:
                existing = merged[key]
                existing_dt = existing.get('datetime_updated', existing.get('datetime', ''))
                new_dt = ann.get('datetime_updated', ann.get('datetime', ''))

                # Keep the more recent one
                if new_dt > existing_dt:
                    merged[key] = ann.copy()
                # If same time but new one has a note and existing doesn't, prefer the one with note
                elif new_dt == existing_dt and ann.get('note') and not existing.get('note'):
                    merged[key] = ann.copy()
            else:
                merged[key] = ann.copy()

    # Sort by page number, then by position
    result = sorted(merged.values(), key=annotation_sort_key)
    duplicates_removed = total_input - len(result)

    return result, duplicates_removed


def lua_escape_string(s: str) -> str:
    """Escape a string for Lua output."""
    result = []
    for char in s:
        if char == '\\':
            result.append('\\\\')
        elif char == '"':
            result.append('\\"')
        elif char == '\n':
            result.append('\\n')
        elif char == '\r':
            result.append('\\r')
        elif char == '\t':
            result.append('\\t')
        elif ord(char) < 32:
            result.append(f'\\{ord(char)}')
        else:
            result.append(char)
    return '"' + ''.join(result) + '"'


def format_lua_value(value: Any, indent: int = 0) -> str:
    """Format a Python value as Lua syntax."""
    indent_str = '    ' * indent
    next_indent = '    ' * (indent + 1)
    
    if value is None:
        return 'nil'
    elif isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, int):
        return str(value)
    elif isinstance(value, float):
        # Format floats nicely
        if value == int(value):
            return str(int(value))
        return str(value)
    elif isinstance(value, str):
        return lua_escape_string(value)
    elif isinstance(value, dict):
        if not value:
            return '{}'
        
        lines = ['{']
        
        # Sort keys: integers first (sorted), then strings (sorted)
        int_keys = sorted(k for k in value.keys() if isinstance(k, int))
        str_keys = sorted(k for k in value.keys() if isinstance(k, str))
        sorted_keys = int_keys + str_keys
        
        for k in sorted_keys:
            v = value[k]
            if isinstance(k, int):
                key_str = f'[{k}]'
            else:
                key_str = f'["{k}"]'
            
            val_str = format_lua_value(v, indent + 1)
            lines.append(f'{next_indent}{key_str} = {val_str},')
        
        lines.append(f'{indent_str}}}')
        return '\n'.join(lines)
    elif isinstance(value, list):
        if not value:
            return '{}'
        
        lines = ['{']
        for i, v in enumerate(value, 1):
            val_str = format_lua_value(v, indent + 1)
            lines.append(f'{next_indent}[{i}] = {val_str},')
        lines.append(f'{indent_str}}}')
        return '\n'.join(lines)
    else:
        return str(value)


def generate_lua_output(data: Dict) -> str:
    """Generate complete Lua file content."""
    lines = ['return {']
    
    # Sort keys for consistent output
    for key in sorted(data.keys()):
        value = data[key]
        val_str = format_lua_value(value, 1)
        lines.append(f'    ["{key}"] = {val_str},')
    
    lines.append('}')
    return '\n'.join(lines)


def _progress_sort_key(d: Dict) -> Tuple:
    """Sort key that ranks a file's reading progress furthest-first."""
    pct = d.get('percent_finished', 0.0) or 0.0
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        pct = 0.0
    page = d.get('current_page', 0) or 0
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 0
    last_open = str(d.get('last_open', '') or '')
    return (pct, page, last_open)


def load_all_data(filepaths: List[str], verbose: bool = False) -> List[Dict]:
    """Parse all input Lua files and return a list of their data dicts.

    Args:
        filepaths: Paths to KOReader .lua metadata files.
        verbose: If True, print annotation counts per file.

    Returns:
        List of parsed data dicts, one per file.
    """
    all_data = []
    for filepath in filepaths:
        print(f"Parsing: {filepath}")
        try:
            data = parse_lua_file(filepath)
            all_data.append(data)
            if verbose:
                ann_count = len(data.get('annotations', {}))
                print(f"  Found {ann_count} annotations")
        except FileNotFoundError:
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error parsing {filepath}: {e}", file=sys.stderr)
            sys.exit(1)
    return all_data


def collect_annotations(all_data: List[Dict], filepaths: List[str]) -> List[List[Dict]]:
    """Extract and normalise the annotation lists from parsed data dicts.

    Args:
        all_data: Parsed data dicts (same order as filepaths).
        filepaths: Original file paths, used only for warning messages.

    Returns:
        List of annotation lists, one per file that contained annotations.
    """
    all_annotations = []
    for data, filepath in zip(all_data, filepaths):
        if 'annotations' not in data:
            continue
        annotations = data['annotations']
        if isinstance(annotations, dict):
            skipped = [k for k in annotations.keys() if not isinstance(k, int)]
            if skipped:
                print(
                    f"Warning: skipping {len(skipped)} non-integer annotation key(s) in "
                    f"{filepath}: {skipped[:5]}",
                    file=sys.stderr,
                )
            annotations = [annotations[k] for k in sorted(annotations.keys()) if isinstance(k, int)]
        all_annotations.append(annotations)
    return all_annotations


def build_output(all_data: List[Dict], merged_annotations: List[Dict],
                 highlights: int, bookmarks: int, notes: int) -> Dict:
    """Assemble the output data dict from merged annotations and source metadata.

    Args:
        all_data: All parsed data dicts (first element is the metadata source).
        merged_annotations: Deduplicated, sorted annotation list.
        highlights: Count of highlight annotations.
        bookmarks: Count of bookmark annotations.
        notes: Count of annotations with a note field.

    Returns:
        Dict ready to be passed to generate_lua_output().
    """
    first_data = all_data[0]

    # Warn if files appear to be from different editions of the book
    checksums = [str(d['partial_md5_checksum']) for d in all_data if d.get('partial_md5_checksum')]
    if len(set(checksums)) > 1:
        print(
            "Warning: partial_md5_checksum differs across input files — files may be from "
            "different editions of the book. Proceeding with metadata from the first file.",
            file=sys.stderr,
        )
    doc_paths = [str(d['doc_path']) for d in all_data if d.get('doc_path')]
    if len(set(doc_paths)) > 1:
        print(
            f"Warning: doc_path differs across input files: {doc_paths}. "
            "Using path from the first file.",
            file=sys.stderr,
        )

    annotations_dict = {
        i: {k: v for k, v in ann.items() if not k.startswith('_')}
        for i, ann in enumerate(merged_annotations, 1)
    }
    output_data: Dict = {'annotations': annotations_dict}

    # Reading progress: pick from the file with the furthest position.
    # Using most-recent timestamp alone would regress position if a device
    # was opened recently but hadn't caught up to where another device was.
    progress_source = max(all_data, key=_progress_sort_key)
    for field in ('current_page', 'percent_finished', 'last_open'):
        if field in progress_source:
            output_data[field] = progress_source[field]

    # Document metadata from the first file
    for field in ('doc_pages', 'doc_path', 'doc_props', 'partial_md5_checksum'):
        if field in first_data:
            output_data[field] = first_data[field]

    # Rebuild stats with fresh annotation counts
    doc_props = first_data.get('doc_props', {})
    output_data['stats'] = {
        'authors': doc_props.get('authors', ''),
        'highlights': highlights,
        'language': doc_props.get('language', ''),
        'notes': notes,
        'pages': first_data.get('doc_pages', 0),
        # KOReader stores per-session reading-speed analytics here; we don't merge it,
        # so emit an empty table to keep the schema valid.
        'performance_in_pages': {},
        'series': doc_props.get('series', ''),
        'title': doc_props.get('title', ''),
    }

    # Summary: take the most recently modified one
    summaries = [d['summary'] for d in all_data if d.get('summary')]
    if summaries:
        summaries.sort(key=lambda x: x.get('modified', '') if isinstance(x, dict) else '', reverse=True)
        output_data['summary'] = summaries[0]

    return output_data


def write_output(content: str, filepath: str, dry_run: bool) -> None:
    """Write Lua content to a file, or report what would be written on dry-run.

    Args:
        content: Lua file content to write.
        filepath: Destination file path.
        dry_run: If True, print a summary instead of writing.
    """
    if dry_run:
        print("\nDry run — no file written.")
        print(f"  Would write {len(content)} bytes to: {filepath}")
    else:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\nOutput written to: {filepath}")
        except Exception as e:
            print(f"Error writing output: {e}", file=sys.stderr)
            sys.exit(1)


def _highlight_text_in_html(html_content: str, ann_text: str, color: str, note: str = '') -> str:
    """Find ann_text in html_content and wrap it with a colored highlight span.

    Tries exact HTML-escaped match first, then raw text match, then whitespace-normalised match.
    Returns html_content unchanged if no match is found.
    """
    if not ann_text:
        return html_content

    note_html = ''
    if note:
        note_escaped = html_module.escape(note, quote=True)
        note_html = f' <span class="ann-note" title="{note_escaped}">[note]</span>'

    def make_span(inner: str) -> str:
        return (
            f'<span style="background-color: {color}; padding: 0 2px;">'
            f'{inner}</span>{note_html}'
        )

    escaped_text = html_module.escape(ann_text)
    if escaped_text in html_content:
        return html_content.replace(escaped_text, make_span(escaped_text), 1)

    if ann_text in html_content:
        return html_content.replace(ann_text, make_span(html_module.escape(ann_text)), 1)

    # Whitespace-normalised fallback
    normalised = re.sub(r'\s+', ' ', ann_text).strip()
    normalised_escaped = html_module.escape(normalised)
    if normalised_escaped in html_content:
        return html_content.replace(normalised_escaped, make_span(normalised_escaped), 1)

    return html_content


def render_annotated_html(
    epub_path: str,
    html_output_path: str,
    annotations: List[Dict],
    file_list: List[str],
    verbose: bool = False,
) -> None:
    """Render epub content with colour-coded annotation highlights to an HTML file.

    Annotations are colour-coded by source device (input file).  A legend at the
    top of the page maps each colour to its source filename.  The resulting HTML
    can be opened in any browser and printed to PDF if needed.

    Args:
        epub_path: Path to the epub file to render.
        html_output_path: Destination HTML file path.
        annotations: Merged annotations; each must carry a ``_device_index`` key
            set before merging (int index into file_list).
        file_list: Ordered list of input .lua file paths (used for legend labels).
        verbose: If True, print per-annotation match status.
    """
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError:
        print(
            "Error: --render-html requires 'ebooklib'.\n"
            "Install with: pip install ebooklib",
            file=sys.stderr,
        )
        sys.exit(1)

    device_colors = {i: DEVICE_COLORS[i % len(DEVICE_COLORS)] for i in range(len(file_list))}

    # Collect (text, color, note) tuples — skip annotations without text
    ann_data: List[Tuple[str, str, str]] = []
    for ann in annotations:
        text = ann.get('text', '')
        if not text:
            continue
        device_idx = ann.get('_device_index', 0)
        color = device_colors.get(device_idx, DEVICE_COLORS[0])
        note = ann.get('note', '') or ''
        ann_data.append((text, color, note))

    # Build legend HTML
    legend_rows = []
    for i, filepath in enumerate(file_list):
        color = device_colors[i]
        name = os.path.basename(filepath)
        legend_rows.append(
            f'  <p style="margin: 4px 0;">'
            f'<span style="background-color: {color}; padding: 2px 10px; margin-right: 8px;">'
            f'&nbsp;&nbsp;&nbsp;&nbsp;</span>{html_module.escape(name)}</p>'
        )
    legend_html = (
        '<div style="font-family: sans-serif; margin: 20px; padding: 12px;'
        ' border: 1px solid #ccc; background: #f9f9f9;">'
        '<h3 style="margin-top: 0;">Annotation Sources</h3>\n'
        + '\n'.join(legend_rows)
        + '\n</div>\n<hr style="margin: 20px 0;">\n'
    )

    # Process epub chapters and apply highlights
    book = epub.read_epub(epub_path)
    chapter_htmls: List[str] = []
    matched_total = 0
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        content = item.get_content().decode('utf-8', errors='replace')
        for ann_text, color, note in ann_data:
            new_content = _highlight_text_in_html(content, ann_text, color, note)
            if new_content is not content and verbose:
                print(f"  Highlighted: {ann_text[:60]!r}")
                matched_total += 1
            content = new_content
        chapter_htmls.append(content)

    if verbose:
        print(f"  {matched_total}/{len(ann_data)} annotations matched in epub text")

    combined_body = '\n<hr style="margin: 30px 0;">\n'.join(chapter_htmls)
    full_html = (
        '<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n'
        '<style>\n'
        'body { font-family: Georgia, serif; font-size: 12pt; line-height: 1.6; margin: 40px; }\n'
        '.ann-note { font-size: 9pt; color: #555; font-style: italic; }\n'
        '</style>\n</head>\n<body>\n'
        + legend_html
        + combined_body
        + '\n</body>\n</html>'
    )

    with open(html_output_path, 'w', encoding='utf-8') as f:
        f.write(full_html)


def render_annotated_pdf(
    pdf_path: str,
    pdf_output_path: str,
    annotations: List[Dict],
    file_list: List[str],
    verbose: bool = False,
) -> None:
    """Render a PDF with colour-coded annotation highlights overlaid per source device.

    Highlights are drawn using the ``pboxes`` bounding boxes from each annotation.
    A legend page is inserted at the start mapping each colour to its source file.
    Notes are attached as popup content on the annotation.

    Args:
        pdf_path: Path to the source PDF file.
        pdf_output_path: Destination PDF file path.
        annotations: Merged annotations; each must carry a ``_device_index`` key.
        file_list: Ordered list of input .lua file paths (used for legend labels).
        verbose: If True, print per-annotation render status.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print(
            "Error: --render-pdf requires 'PyMuPDF'.\n"
            "Install with: pip install PyMuPDF",
            file=sys.stderr,
        )
        sys.exit(1)

    device_colors = {i: DEVICE_COLORS[i % len(DEVICE_COLORS)] for i in range(len(file_list))}

    # Group annotations by page number (1-indexed); skip those without pboxes
    page_annotations: Dict[int, List[Dict]] = {}
    for ann in annotations:
        if not ann.get('pboxes'):
            continue
        pageno = ann.get('pageno') or ann.get('page')
        if pageno is None:
            continue
        page_annotations.setdefault(int(pageno), []).append(ann)

    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    rendered = 0
    skipped_oob = 0

    for pageno, ann_list in page_annotations.items():
        # PyMuPDF uses 0-indexed pages
        page_idx = pageno - 1
        if page_idx < 0 or page_idx >= total_pages:
            if verbose:
                print(f"  Warning: page {pageno} out of range (PDF has {total_pages} pages), skipping")
            skipped_oob += len(ann_list)
            continue

        page = doc[page_idx]
        for ann in ann_list:
            device_idx = ann.get('_device_index', 0)
            rgb = _hex_to_rgb(device_colors[device_idx])
            pboxes = ann['pboxes']
            # pboxes is parsed as {1: {...}, 2: {...}} by the Lua parser
            pb_list = pboxes.values() if isinstance(pboxes, dict) else pboxes
            rects = [
                fitz.Rect(pb['x'], pb['y'], pb['x'] + pb['w'], pb['y'] + pb['h'])
                for pb in pb_list
            ]
            highlight = page.add_highlight_annot(quads=rects)
            highlight.set_colors(stroke=rgb)
            highlight.set_opacity(0.5)
            note = ann.get('note', '') or ''
            if note:
                highlight.set_info(content=note)
            highlight.update()
            rendered += 1
            if verbose:
                text_preview = (ann.get('text') or '')[:60]
                print(f"  Page {pageno}: highlighted {text_preview!r}")

    if skipped_oob and not verbose:
        print(f"  Warning: {skipped_oob} annotation(s) skipped (page out of range)")

    # Insert legend page at position 0
    legend = doc.new_page(pno=0, width=612, height=792)
    legend.insert_text((72, 72), "Annotation Sources", fontsize=18, fontname="helv")
    for i, filepath in enumerate(file_list):
        y_pos = 110 + i * 30
        rgb = _hex_to_rgb(device_colors[i])
        swatch = fitz.Rect(72, y_pos, 112, y_pos + 18)
        legend.draw_rect(swatch, color=rgb, fill=rgb, fill_opacity=0.5)
        legend.insert_text((120, y_pos + 14), os.path.basename(filepath), fontsize=12, fontname="helv")

    doc.save(pdf_output_path, garbage=4, deflate=True)
    doc.close()

    if verbose:
        print(f"  {rendered} annotation(s) rendered across {len(page_annotations)} page(s)")


def main():
    parser = argparse.ArgumentParser(
        description='Merge KOReader annotations from multiple devices.',
        epilog='Example: %(prog)s device1.lua device2.lua -o merged.lua'
    )
    parser.add_argument(
        'files',
        nargs='+',
        metavar='FILE',
        help='Input Lua metadata files from KOReader'
    )
    parser.add_argument(
        '-o', '--output',
        required=True,
        metavar='OUTPUT',
        help='Output Lua file path'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed information about merged annotations'
    )
    parser.add_argument(
        '-n', '--dry-run',
        action='store_true',
        help='Show what would be written without actually writing the output file'
    )
    parser.add_argument(
        '--render-html',
        action='store_true',
        help='Render the epub with colour-coded annotation highlights to an HTML file'
    )
    parser.add_argument(
        '--epub',
        metavar='EPUB',
        help='Path to the epub file (required when --render-html is used)'
    )
    parser.add_argument(
        '--html-output',
        metavar='HTML',
        help='Output HTML file path (default: output path with .html extension)'
    )
    parser.add_argument(
        '--render-pdf',
        action='store_true',
        help='Render the PDF with colour-coded annotation highlights overlaid (requires PyMuPDF)'
    )
    parser.add_argument(
        '--pdf',
        metavar='PDF',
        help='Path to the source PDF file (required when --render-pdf is used)'
    )
    parser.add_argument(
        '--pdf-output',
        metavar='PDF_OUT',
        help='Output PDF file path (default: output path with .pdf extension)'
    )

    args = parser.parse_args()

    # Infer --render-html when --epub or --html-output is given
    if args.epub or args.html_output:
        args.render_html = True

    if args.render_html:
        if not args.epub:
            parser.error('--epub is required when --render-html is used')
        if not os.path.isfile(args.epub):
            parser.error(f'epub file not found: {args.epub}')

    # Infer --render-pdf when --pdf or --pdf-output is given
    if args.pdf or args.pdf_output:
        args.render_pdf = True

    if args.render_pdf:
        if not args.pdf:
            parser.error('--pdf is required when --render-pdf is used')
        if not os.path.isfile(args.pdf):
            parser.error(f'PDF file not found: {args.pdf}')

    all_data = load_all_data(args.files, verbose=args.verbose)
    all_annotations = collect_annotations(all_data, args.files)

    # Tag each annotation with its source device index so the PDF renderer can colour-code it
    for device_idx, ann_list in enumerate(all_annotations):
        for ann in ann_list:
            ann['_device_index'] = device_idx

    merged_annotations, duplicates_removed = merge_annotations(all_annotations)

    highlights = sum(1 for ann in merged_annotations if 'pos0' in ann)
    bookmarks = len(merged_annotations) - highlights
    notes = sum(1 for ann in merged_annotations if ann.get('note'))

    print("\nMerged results:")
    print(f"  Total annotations: {len(merged_annotations)}")
    print(f"  Highlights: {highlights}")
    print(f"  Bookmarks: {bookmarks}")
    print(f"  Notes: {notes}")
    if args.verbose and duplicates_removed > 0:
        print(f"  Duplicates removed: {duplicates_removed}")

    output_data = build_output(all_data, merged_annotations, highlights, bookmarks, notes)
    output_content = generate_lua_output(output_data)
    write_output(output_content, args.output, dry_run=args.dry_run)

    if args.render_html:
        html_path: str = args.html_output or os.path.splitext(args.output)[0] + '.html'
        render_annotated_html(
            epub_path=args.epub,
            html_output_path=html_path,
            annotations=merged_annotations,
            file_list=args.files,
            verbose=args.verbose,
        )
        print(f"HTML written to: {html_path}")

    if args.render_pdf:
        pdf_out_path: str = args.pdf_output or os.path.splitext(args.output)[0] + '.pdf'
        render_annotated_pdf(
            pdf_path=args.pdf,
            pdf_output_path=pdf_out_path,
            annotations=merged_annotations,
            file_list=args.files,
            verbose=args.verbose,
        )
        print(f"Annotated PDF written to: {pdf_out_path}")


if __name__ == '__main__':
    main()