"""Tests for merge_koreader.py"""

import os
import sys
import tempfile
from unittest.mock import patch

import pytest

# Make the parent directory importable when running from tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from merge_koreader import (
    annotation_key,
    build_output,
    collect_annotations,
    format_lua_value,
    generate_lua_output,
    lua_escape_string,
    main,
    merge_annotations,
    parse_lua_file,
    parse_lua_string,
    parse_lua_table,
    parse_lua_value,
    render_annotated_html,
    render_annotated_pdf,
    validate_input_compatibility,
    _highlight_text_in_html,
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

    def test_control_character_before_digit_round_trips(self):
        value = '\x011\x0012\x1f9'
        encoded = lua_escape_string(value)
        decoded, _ = parse_lua_string(encoded, 0)
        assert decoded == value
        assert '\\0011' in encoded

    def test_escaped_dictionary_keys_round_trip(self):
        value = {'quote"key': 'a', 'slash\\key': 'b'}
        encoded = format_lua_value(value)
        decoded, _ = parse_lua_table(encoded, 0)
        assert decoded == value


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

    def test_pdf_zoom_and_rotation_do_not_change_identity(self):
        first = self._ann(10.0, 100.0, 1, '2024-01-01 00:00:00')
        first['pos0'].update({'zoom': 1.0, 'rotation': 0})
        first['pos1'].update({'zoom': 1.0, 'rotation': 0})
        second = {**first, 'datetime_updated': '2024-01-02 00:00:00'}
        second['pos0'] = {**first['pos0'], 'zoom': 2.0, 'rotation': 90}
        second['pos1'] = {**first['pos1'], 'zoom': 2.0, 'rotation': 90}
        assert annotation_key(first) == annotation_key(second)
        merged, duplicates = merge_annotations([[first], [second]])
        assert len(merged) == 1
        assert duplicates == 1
        assert merged[0]['datetime_updated'] == '2024-01-02 00:00:00'

    def test_annotations_sort_by_page_before_kind(self):
        early_bookmark = {'page': 2, 'chapter': 'Early'}
        late_highlight = self._ann(10.0, 100.0, 50, '2024-01-01 00:00:00')
        merged, _ = merge_annotations([[late_highlight, early_bookmark]])
        assert merged == [early_bookmark, late_highlight]


class TestCollectAnnotations:
    def test_preserves_one_group_per_input(self, capsys):
        annotation = {'page': 1}
        groups = collect_annotations(
            [{}, {'annotations': {1: annotation, 'metadata': {}}}],
            ['empty.lua', 'annotated.lua'],
        )
        assert groups == [[], [annotation]]
        assert 'non-integer annotation key' in capsys.readouterr().err

    def test_rejects_legacy_annotation_format(self):
        with pytest.raises(ValueError, match='legacy KOReader annotation fields'):
            collect_annotations([{'bookmarks': {1: {'page': 1}}}], ['legacy.lua'])

    def test_rejects_malformed_annotation_entries(self):
        with pytest.raises(ValueError, match='Invalid annotation 1'):
            collect_annotations([{'annotations': {1: 'bad'}}], ['bad.lua'])

    def test_rejects_conflicting_dom_versions(self):
        with pytest.raises(ValueError, match='different cre_dom_version'):
            validate_input_compatibility(
                [{'cre_dom_version': 1}, {'cre_dom_version': 2}],
                ['a.lua', 'b.lua'],
            )

    def test_warns_when_epub_dom_version_is_missing(self, capsys):
        data = {'annotations': {1: {'pos0': '/body/DocFragment[1]/body/p/text().0'}}}
        validate_input_compatibility([data], ['missing-version.lua'])
        assert 'compatibility could not be verified' in capsys.readouterr().err


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

    def test_uses_last_page_for_paged_documents(self):
        behind = {'percent_finished': 0.1, 'last_page': 5}
        ahead = {'percent_finished': 0.1, 'last_page': 10}
        assert max([behind, ahead], key=_progress_sort_key) is ahead


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

    def test_preserves_resume_and_refresh_metadata(self):
        sources = [
            {'annotations': {}, 'percent_finished': 0.1, 'last_page': 10},
            {
                'annotations': {},
                'percent_finished': 0.5,
                'last_xpointer': '/body/DocFragment[2]/body/p/text().3',
                'cre_dom_version': 20240114,
            },
        ]
        out = build_output(sources, [], 0, 0, 0)
        assert out['last_xpointer'].endswith('text().3')
        assert out['cre_dom_version'] == 20240114
        assert out['annotations_externally_modified'] is True


class TestCliBehavior:
    def test_dry_run_never_writes_or_renders(self, tmp_path, capsys):
        epub_path = tmp_path / 'book.epub'
        pdf_path = tmp_path / 'book.pdf'
        epub_path.write_bytes(b'placeholder')
        pdf_path.write_bytes(b'placeholder')
        output_path = tmp_path / 'merged.lua'
        argv = [
            'merge_koreader.py', DEVICE_A, '-o', str(output_path), '--dry-run',
            '--epub', str(epub_path), '--pdf', str(pdf_path),
        ]
        with patch.object(sys, 'argv', argv), patch(
            'merge_koreader.render_annotated_html'
        ) as render_html, patch('merge_koreader.render_annotated_pdf') as render_pdf:
            main()
        assert not output_path.exists()
        render_html.assert_not_called()
        render_pdf.assert_not_called()
        output = capsys.readouterr().out
        assert 'Would render HTML' in output
        assert 'Would render annotated PDF' in output


class TestHtmlRendering:
    def test_visible_text_matching_preserves_attributes_and_inline_markup(self):
        source = '<p title="Hello world">Hello <em>world</em></p>'
        rendered = _highlight_text_in_html(source, 'Hello world', '#FFFF99', 'note')
        assert 'title="Hello world"' in rendered
        assert '<em><span' in rendered
        assert rendered.count('annotation-highlight') == 2
        assert rendered.count('ann-note') == 1

    def test_ambiguous_visible_text_is_unchanged(self):
        source = '<p>repeat me and repeat me</p>'
        assert _highlight_text_in_html(source, 'repeat me', '#FFFF99') == source

    def test_epub_uses_spine_positions_and_skips_ambiguous_fallback(self, tmp_path, capsys):
        ebooklib = pytest.importorskip('ebooklib')
        from ebooklib import epub
        from lxml import html

        book = epub.EpubBook()
        book.set_identifier('test-book')
        book.set_title('Test Book')
        book.set_language('en')
        later = epub.EpubHtml(uid='later', file_name='later.xhtml', title='Later')
        later.content = '<html><body><p>Manifest first.</p></body></html>'
        first = epub.EpubHtml(uid='first', file_name='first.xhtml', title='First')
        first.content = (
            '<html><body><p>Spine first has <em>inline text</em>.</p>'
            '<p>repeat me and repeat me</p></body></html>'
        )
        book.add_item(later)
        book.add_item(first)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = [first, later]
        epub_path = tmp_path / 'book.epub'
        output_path = tmp_path / 'rendered.html'
        epub.write_epub(str(epub_path), book)
        annotations = [
            {
                'text': 'Spine first has inline text',
                'note': 'inline note',
                'pos0': '/body/DocFragment[1]/body/p[1]/text().0',
                'pos1': '/body/DocFragment[1]/body/p[1]/em/text().11',
                '_device_index': 0,
            },
            {
                'text': 'repeat me',
                'pos0': '/body/DocFragment[1]/body/p[99]/text().0',
                'pos1': '/body/DocFragment[1]/body/p[99]/text().9',
                '_device_index': 0,
            },
        ]
        render_annotated_html(
            str(epub_path), str(output_path), annotations, ['device.lua']
        )
        rendered = output_path.read_text(encoding='utf-8')
        document = html.fromstring(rendered)
        assert len(document.xpath('//html')) == 1
        assert len(document.xpath('//span[@class="ann-note"]')) == 1
        assert rendered.index('Spine first') < rendered.index('Manifest first')
        summary = capsys.readouterr().out
        assert '1 matched, 0 unmatched, 1 ambiguous' in summary
        assert ebooklib.ITEM_DOCUMENT


class TestPdfRendering:
    def test_renders_each_page_of_extended_highlight(self, tmp_path):
        fitz = pytest.importorskip('fitz')
        source_path = tmp_path / 'source.pdf'
        output_path = tmp_path / 'output.pdf'
        source = fitz.open()
        source.new_page()
        source.new_page()
        source.save(str(source_path))
        source.close()
        boxes = {1: {'x': 20, 'y': 20, 'w': 100, 'h': 20}}
        annotation = {
            'text': 'two pages',
            'note': 'popup note',
            'pos0': {'page': 1, 'x': 20, 'y': 20},
            'pos1': {'page': 2, 'x': 120, 'y': 40},
            'ext': {1: {'pboxes': boxes}, 2: {'pboxes': boxes}},
            '_device_index': 0,
        }
        render_annotated_pdf(
            str(source_path), str(output_path), [annotation], ['device.lua']
        )
        rendered = fitz.open(str(output_path))
        try:
            assert rendered.page_count == 3
            annotations = [list(rendered[index].annots() or []) for index in (1, 2)]
            assert [len(items) for items in annotations] == [1, 1]
            assert all(items[0].info['content'] == 'popup note' for items in annotations)
        finally:
            rendered.close()


def test_installer_uses_validated_python_command():
    installer_path = os.path.join(os.path.dirname(__file__), '..', 'install.sh')
    with open(installer_path, encoding='utf-8') as installer_file:
        installer = installer_file.read()
    assert '#!/usr/bin/env ${PYTHON}' in installer
    assert '${PYTHON} -m pip install ebooklib' in installer
