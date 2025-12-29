#!/usr/bin/env python3
"""
Merge KOReader annotations from multiple devices.

Usage: python merge_koreader.py file1.lua file2.lua [file3.lua ...] -o output.lua
"""

import argparse
import re
import sys
from typing import Any, Dict, List, Tuple


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
    if s[pos:pos+4] == 'true' and (pos + 4 >= len(s) or not s[pos+4].isalnum()):
        return True, pos + 4
    if s[pos:pos+5] == 'false' and (pos + 5 >= len(s) or not s[pos+5].isalnum()):
        return False, pos + 5
    if s[pos:pos+3] == 'nil' and (pos + 3 >= len(s) or not s[pos+3].isalnum()):
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


def annotation_key(ann: Dict) -> Tuple:
    """Generate a unique key for an annotation to detect duplicates."""
    # For highlights with position data
    if 'pos0' in ann and 'pos1' in ann:
        return ('highlight', ann.get('pos0'), ann.get('pos1'))
    # For bookmarks without position data, use page location
    return ('bookmark', ann.get('page'), ann.get('chapter'))


def merge_annotations(annotations_list: List[List[Dict]]) -> List[Dict]:
    """Merge annotations from multiple sources, keeping the most recent version."""
    merged = {}
    
    for annotations in annotations_list:
        for ann in annotations:
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
    result = sorted(merged.values(), key=lambda x: (
        x.get('pageno', 0),
        x.get('pos0', ''),
        x.get('datetime', '')
    ))
    
    return result


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
    
    args = parser.parse_args()
    
    if len(args.files) < 1:
        print("Error: At least one input file required.", file=sys.stderr)
        sys.exit(1)
    
    # Parse all input files
    all_data = []
    for filepath in args.files:
        print(f"Parsing: {filepath}")
        try:
            data = parse_lua_file(filepath)
            all_data.append(data)
            
            if args.verbose:
                ann_count = len(data.get('annotations', {}))
                print(f"  Found {ann_count} annotations")
                
        except FileNotFoundError:
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error parsing {filepath}: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Collect annotations from all files
    all_annotations = []
    for data in all_data:
        if 'annotations' in data:
            annotations = data['annotations']
            if isinstance(annotations, dict):
                # Convert dict with integer keys to list
                annotations = [annotations[k] for k in sorted(annotations.keys()) if isinstance(k, int)]
            all_annotations.append(annotations)
    
    # Merge annotations
    merged_annotations = merge_annotations(all_annotations)
    
    # Count highlights vs bookmarks
    highlights = sum(1 for ann in merged_annotations if 'pos0' in ann)
    bookmarks = len(merged_annotations) - highlights
    notes = sum(1 for ann in merged_annotations if ann.get('note'))
    
    print(f"\nMerged results:")
    print(f"  Total annotations: {len(merged_annotations)}")
    print(f"  Highlights: {highlights}")
    print(f"  Bookmarks: {bookmarks}")
    print(f"  Notes: {notes}")
    
    # Convert to dict with integer keys (Lua array format)
    annotations_dict = {i: ann for i, ann in enumerate(merged_annotations, 1)}
    
    # Use first file as source for metadata
    first_data = all_data[0]
    
    # Build output with only essential data (no display settings)
    output_data = {
        'annotations': annotations_dict,
    }
    
    # Include document metadata
    if 'doc_pages' in first_data:
        output_data['doc_pages'] = first_data['doc_pages']
    
    if 'doc_path' in first_data:
        output_data['doc_path'] = first_data['doc_path']
    
    if 'doc_props' in first_data:
        output_data['doc_props'] = first_data['doc_props']
    
    if 'partial_md5_checksum' in first_data:
        output_data['partial_md5_checksum'] = first_data['partial_md5_checksum']
    
    # Build updated stats
    doc_props = first_data.get('doc_props', {})
    output_data['stats'] = {
        'authors': doc_props.get('authors', ''),
        'highlights': highlights,
        'language': doc_props.get('language', ''),
        'notes': notes,
        'pages': first_data.get('doc_pages', 0),
        'performance_in_pages': {},
        'series': 'N/A',
        'title': doc_props.get('title', ''),
    }
    
    # Include summary if present (take most recent)
    summaries = [d.get('summary') for d in all_data if d.get('summary')]
    if summaries:
        # Sort by modified date and take the most recent
        summaries.sort(key=lambda x: x.get('modified', ''), reverse=True)
        output_data['summary'] = summaries[0]
    
    # Generate and write output
    output_content = generate_lua_output(output_data)
    
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_content)
        print(f"\nOutput written to: {args.output}")
    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()