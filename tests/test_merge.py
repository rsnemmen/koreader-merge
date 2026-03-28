"""Tests for merge_koreader.py"""

import os
import sys
import tempfile

import pytest

# Make the parent directory importable when running from tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from merge_koreader import (
    annotation_key,
    build_output,
    collect_annotations,
    generate_lua_output,
    merge_annotations,
    parse_lua_file,
    parse_lua_string,
    parse_lua_table,
    parse_lua_value,
    _progress_sort_key,
)

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
DEVICE_A = os.path.join(FIXTURES, 'device_a.lua')
DEVICE_B = os.path.join(FIXTURES, 'device_b.lua')


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestParseLuaString:
    def test_simple(self):
        val, pos = parse_lua_string('"hello"', 0)
        assert val == 'hello'
        assert pos == 7

    def test_escape_newline(self):
        val, _ = parse_lua_string(r'"line1\nline2"', 0)
        assert val == 'line1\nline2'

    def test_escape_tab(self):
        val, _ = parse_lua_string(r'"a\tb"', 0)
        assert val == 'a\tb'

    def test_escape_backslash(self):
        val, _ = parse_lua_string(r'"a\\b"', 0)
        assert val == 'a\\b'

    def test_hex_escape_valid(self):
        val, _ = parse_lua_string('"\\x41"', 0)  # \x41 == 'A'
        assert val == 'A'

    def test_hex_escape_invalid_emits_literal(self):
        # Invalid hex: should emit \x literally rather than corrupting
        val, _ = parse_lua_string('"\\xGG"', 0)
        assert val == '\\xGG'

    def test_decimal_escape(self):
        val, _ = parse_lua_string('"\\65"', 0)  # \65 == 'A'
        assert val == 'A'

    def test_single_quotes(self):
        val, _ = parse_lua_string("'hello'", 0)
        assert val == 'hello'


class TestParseLuaValue:
    def test_true(self):
        val, pos = parse_lua_value('true', 0)
        assert val is True
        assert pos == 4

    def test_false(self):
        val, pos = parse_lua_value('false', 0)
        assert val is False
        assert pos == 5

    def test_nil(self):
        val, pos = parse_lua_value('nil', 0)
        assert val is None
        assert pos == 3

    def test_true_with_underscore_not_keyword(self):
        # 'true_value' should NOT parse as the keyword true
        with pytest.raises(ValueError):
            parse_lua_value('true_value', 0)

    def test_false_with_underscore_not_keyword(self):
        with pytest.raises(ValueError):
            parse_lua_value('false_flag', 0)

    def test_nil_with_underscore_not_keyword(self):
        with pytest.raises(ValueError):
            parse_lua_value('nil_check', 0)

    def test_integer(self):
        val, pos = parse_lua_value('42', 0)
        assert val == 42
        assert isinstance(val, int)

    def test_float(self):
        val, _ = parse_lua_value('3.14', 0)
        assert abs(val - 3.14) < 1e-9
        assert isinstance(val, float)

    def test_negative_integer(self):
        val, _ = parse_lua_value('-7', 0)
        assert val == -7

    def test_scientific_notation(self):
        val, _ = parse_lua_value('1e3', 0)
        assert val == 1000.0

    def test_string(self):
        val, _ = parse_lua_value('"hello"', 0)
        assert val == 'hello'

    def test_nested_table(self):
        val, _ = parse_lua_value('{ ["x"] = 1, ["y"] = 2 }', 0)
        assert val == {'x': 1, 'y': 2}

    def test_boolean_in_table(self):
        val, _ = parse_lua_value('{ ["flag"] = true }', 0)
        assert val == {'flag': True}


class TestParseLuaTable:
    def test_empty_table(self):
        val, _ = parse_lua_table('{}', 0)
        assert val == {}

    def test_string_keys(self):
        val, _ = parse_lua_table('{ ["a"] = 1, ["b"] = 2 }', 0)
        assert val == {'a': 1, 'b': 2}

    def test_integer_keys(self):
        val, _ = parse_lua_table('{ [1] = "x", [2] = "y" }', 0)
        assert val == {1: 'x', 2: 'y'}

    def test_identifier_keys(self):
        val, _ = parse_lua_table('{ foo = 1, bar = 2 }', 0)
        assert val == {'foo': 1, 'bar': 2}

    def test_nested(self):
        val, _ = parse_lua_table('{ ["inner"] = { ["x"] = 99 } }', 0)
        assert val == {'inner': {'x': 99}}

    def test_trailing_comma(self):
        val, _ = parse_lua_table('{ ["a"] = 1, }', 0)
        assert val == {'a': 1}

    def test_long_string_value(self):
        val, _ = parse_lua_table('{ ["text"] = [[hello\nworld]] }', 0)
        assert val == {'text': 'hello\nworld'}


# ---------------------------------------------------------------------------
# Round-trip test
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_parse_serialize_reparse(self):
        data_a = parse_lua_file(DEVICE_A)
        lua_out = generate_lua_output(data_a)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False, encoding='utf-8') as f:
            f.write(lua_out)
            tmp = f.name

        try:
            reparsed = parse_lua_file(tmp)
        finally:
            os.unlink(tmp)

        # Key annotations should survive round-trip
        assert len(reparsed['annotations']) == len(data_a['annotations'])
        assert reparsed['doc_path'] == data_a['doc_path']
        assert reparsed['doc_pages'] == data_a['doc_pages']


# ---------------------------------------------------------------------------
# Merge / deduplication tests
# ---------------------------------------------------------------------------

class TestMergeAnnotations:
    def _ann(self, pos0_x: float, pos0_y: float, page: int,
             dt: str, note: str = '') -> dict:
        a = {
            'page': page,
            'pos0': {'page': page, 'x': pos0_x, 'y': pos0_y},
            'pos1': {'page': page, 'x': pos0_x + 100, 'y': pos0_y},
            'datetime': dt,
            'datetime_updated': dt,
            'text': 'sample',
        }
        if note:
            a['note'] = note
        return a

    def test_no_duplicates_distinct_positions(self):
        a = self._ann(10.0, 100.0, 1, '2024-01-01 00:00:00')
        b = self._ann(20.0, 200.0, 2, '2024-01-01 00:00:00')
        merged, dupes = merge_annotations([[a, b]])
        assert len(merged) == 2
        assert dupes == 0

    def test_duplicate_same_file(self):
        a = self._ann(10.0, 100.0, 1, '2024-01-01 00:00:00')
        merged, dupes = merge_annotations([[a, a]])
        assert len(merged) == 1
        assert dupes == 1

    def test_newer_datetime_wins(self):
        old = self._ann(10.0, 100.0, 1, '2024-01-01 00:00:00')
        new = {**old, 'datetime_updated': '2024-01-02 00:00:00', 'text': 'updated'}
        merged, _ = merge_annotations([[old], [new]])
        assert merged[0]['text'] == 'updated'

    def test_older_does_not_overwrite_newer(self):
        new = self._ann(10.0, 100.0, 1, '2024-01-02 00:00:00')
        old = {**new, 'datetime_updated': '2024-01-01 00:00:00', 'text': 'old'}
        merged, _ = merge_annotations([[new], [old]])
        assert merged[0]['datetime_updated'] == '2024-01-02 00:00:00'

    def test_same_time_note_wins_over_no_note(self):
        base = self._ann(10.0, 100.0, 1, '2024-01-01 00:00:00')
        with_note = {**base, 'note': 'important'}
        merged, _ = merge_annotations([[base], [with_note]])
        assert merged[0].get('note') == 'important'

    def test_two_identical_files_no_dupes(self):
        data = parse_lua_file(DEVICE_A)
        anns_a = collect_annotations([data], [DEVICE_A])[0]
        anns_b = list(anns_a)  # identical copy
        merged, dupes = merge_annotations([anns_a, anns_b])
        assert dupes == len(anns_a)
        assert len(merged) == len(anns_a)

    def test_merge_two_devices(self):
        data_a = parse_lua_file(DEVICE_A)
        data_b = parse_lua_file(DEVICE_B)
        all_anns = collect_annotations([data_a, data_b], [DEVICE_A, DEVICE_B])
        merged, dupes = merge_annotations(all_anns)
        # annotation 1 is shared (same pos0/pos1), so 1 dupe; 2 unique from each = 3 total
        assert dupes == 1
        assert len(merged) == 3


# ---------------------------------------------------------------------------
# Reading progress selection
# ---------------------------------------------------------------------------

class TestProgressSortKey:
    def test_prefers_furthest_percent(self):
        behind = {'percent_finished': 0.10, 'current_page': 5, 'last_open': '2024-01-15 00:00:00'}
        ahead = {'percent_finished': 0.50, 'current_page': 3, 'last_open': '2024-01-01 00:00:00'}
        assert max([behind, ahead], key=_progress_sort_key) is ahead

    def test_ties_broken_by_page(self):
        a = {'percent_finished': 0.10, 'current_page': 10, 'last_open': '2024-01-01 00:00:00'}
        b = {'percent_finished': 0.10, 'current_page': 20, 'last_open': '2024-01-01 00:00:00'}
        assert max([a, b], key=_progress_sort_key) is b

    def test_ties_broken_by_last_open(self):
        a = {'percent_finished': 0.10, 'current_page': 10, 'last_open': '2024-01-01 00:00:00'}
        b = {'percent_finished': 0.10, 'current_page': 10, 'last_open': '2024-01-02 00:00:00'}
        assert max([a, b], key=_progress_sort_key) is b

    def test_device_b_further_than_a(self):
        data_a = parse_lua_file(DEVICE_A)
        data_b = parse_lua_file(DEVICE_B)
        # device_b is at 18%, device_a is at 5%
        assert max([data_a, data_b], key=_progress_sort_key) is data_b


# ---------------------------------------------------------------------------
# build_output tests
# ---------------------------------------------------------------------------

class TestBuildOutput:
    def test_progress_from_furthest_device(self):
        data_a = parse_lua_file(DEVICE_A)
        data_b = parse_lua_file(DEVICE_B)
        all_data = [data_a, data_b]
        all_anns = collect_annotations(all_data, [DEVICE_A, DEVICE_B])
        merged, _ = merge_annotations(all_anns)
        highlights = sum(1 for a in merged if 'pos0' in a)
        notes = sum(1 for a in merged if a.get('note'))
        out = build_output(all_data, merged, highlights, len(merged) - highlights, notes)
        # device_b has percent_finished=0.18, device_a has 0.05
        assert out['percent_finished'] == pytest.approx(0.18)
        assert out['current_page'] == 55

    def test_stats_annotation_counts(self):
        data_a = parse_lua_file(DEVICE_A)
        data_b = parse_lua_file(DEVICE_B)
        all_data = [data_a, data_b]
        all_anns = collect_annotations(all_data, [DEVICE_A, DEVICE_B])
        merged, _ = merge_annotations(all_anns)
        highlights = sum(1 for a in merged if 'pos0' in a)
        notes = sum(1 for a in merged if a.get('note'))
        out = build_output(all_data, merged, highlights, len(merged) - highlights, notes)
        assert out['stats']['highlights'] == highlights
        assert out['stats']['notes'] == notes

    def test_metadata_checksum_warning(self, capsys):
        data_a = parse_lua_file(DEVICE_A)
        data_b = {**parse_lua_file(DEVICE_B), 'partial_md5_checksum': 'different_checksum'}
        all_data = [data_a, data_b]
        all_anns = collect_annotations(all_data, [DEVICE_A, DEVICE_B])
        merged, _ = merge_annotations(all_anns)
        highlights = sum(1 for a in merged if 'pos0' in a)
        notes = sum(1 for a in merged if a.get('note'))
        build_output(all_data, merged, highlights, len(merged) - highlights, notes)
        captured = capsys.readouterr()
        assert 'partial_md5_checksum' in captured.err
