#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xml_compare_to_excel.py
------------------------
This script compares two XML files (Before & After), identifies all the differences (element, attribute, and text), and generates a report in an Excel sheet with the following details:

S.No + Location (XML path) + Change Type + Before Value + After Value

USAGE:

In the "INPUT / OUTPUT SETTINGS" section below, specify the file paths for the BEFORE XML, AFTER XML, and the output Excel file.
Run the following command in the terminal:
python3 xml_compare_to_excel.py
The output Excel file will be generated at the specified location.

This script works with any XML files (generic). It matches elements based on their tag/class and uses difflib for alignment. Therefore, if an element is added or removed at one location, the elements below it will not be incorrectly matched due to the resulting shift.
"""

import xml.etree.ElementTree as ET
import xml.parsers.expat as expat
import difflib
import re
import html
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont

# ============================================================
#                 INPUT / OUTPUT SETTINGS
# ============================================================
BEFORE_XML_PATH = "/mnt/user-data/uploads/tx2_-_Copy.xml"   # <-- Before (original) xml path
AFTER_XML_PATH  = "/mnt/user-data/uploads/tx2.xml"          # <-- After (changed) xml path
OUTPUT_EXCEL_PATH = "/mnt/user-data/outputs/xml_compare_report.xlsx"  # <-- Output excel path

# Standalone, colour-coded HTML mistake report (same rows as the excel
# report above, but as a single .html file you can open in any browser
# or email/share - no Excel needed). Set to None to skip generating it.
OUTPUT_HTML_PATH = "/mnt/user-data/outputs/xml_mistake_report.html"

# Marked-up (annotated) copies of before/after XML - a comment such as
# "<!-- >>> CHANGE #<S.No> ... -->" is added above each line where a change
# occurs, so you can use Ctrl+F in Notepad++ to search for "CHANGE #12"
# and jump directly to that change (no line number is needed). Set to False to skip generating these files.
GENERATE_ANNOTATED_COPIES = True
ANNOTATED_BEFORE_PATH = "/mnt/user-data/outputs/before_ANNOTATED.xml"
ANNOTATED_AFTER_PATH = "/mnt/user-data/outputs/after_ANNOTATED.xml"

# List of attributes to ignore during comparison (optional).
# For example: ["data-fieldcode"] - differences in this attribute will not be included in the report. If an empty list is provided, all attributes will be checked
# irundhalum report la varathu. Empty list vachirundha ellame check aagum.
IGNORE_ATTRIBUTES = []

# will not be included in the report. If an empty list is provided, all attributes will be checked.
# Whether it should be ignored (recommended: True)
IGNORE_WHITESPACE_ONLY_DIFF = True
# ============================================================


def parse_with_line_numbers(path):
    """XML file ah parse pannitu, ovoru element ku adhu start aagura
    LINE NUMBER um track pannum (Excel la 'Go to line' mari kaatanumnu)."""
    tb = ET.TreeBuilder()
    line_map = {}  # id(element) -> line number in the source file

    parser = expat.ParserCreate()
    parser.buffer_text = True

    def start(tag, attrs):
        el = tb.start(tag, attrs)
        line_map[id(el)] = parser.CurrentLineNumber

    def end(tag):
        tb.end(tag)

    def data(text):
        tb.data(text)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = data

    with open(path, "rb") as f:
        parser.ParseFile(f)

    root = tb.close()
    return ET.ElementTree(root), line_map


def norm(text):
    """Whitespace normalize pannurathuku (compare panna mattum)."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def local_tag(tag):
    """Namespace irundha remove pannurathuku."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def elem_key_attr(elem):
    """Element ah identify panna use panra 'key' attribute (class irundha
    andha, illana id, illana ellam empty)."""
    return elem.get("class") or elem.get("id") or ""


def elem_signature(elem):
    """Element oda 'fingerprint' - align/match panna use pannuvom."""
    cls = elem_key_attr(elem)
    txt = norm(elem.text)[:60]
    return f"{local_tag(elem.tag)}|{cls}|{txt}"


def elem_signature_loose(elem):
    """Text ah consider pannama, tag+class mattum vachu loose match."""
    cls = elem_key_attr(elem)
    return f"{local_tag(elem.tag)}|{cls}"


def short_desc(elem, max_len=80):
    """Element oru summary - Excel la Before/After column la kaatura mathiri."""
    if elem is None:
        return ""
    tag = local_tag(elem.tag)
    cls = elem_key_attr(elem)
    txt = norm(elem.text)
    label = f"<{tag}" + (f" class='{cls}'" if cls else "") + ">"
    if txt:
        if len(txt) > max_len:
            txt = txt[:max_len] + "..."
        return f"{label} {txt}"
    return label


class DiffRow:
    __slots__ = ("path", "change_type", "before", "after", "before_line", "after_line")

    def __init__(self, path, change_type, before, after, before_line=None, after_line=None):
        self.path = path
        self.change_type = change_type
        self.before = before
        self.after = after
        self.before_line = before_line
        self.after_line = after_line


ROWS = []
BEFORE_LINE_MAP = {}
AFTER_LINE_MAP = {}


def bline(elem):
    return BEFORE_LINE_MAP.get(id(elem)) if elem is not None else None


def aline(elem):
    return AFTER_LINE_MAP.get(id(elem)) if elem is not None else None


def build_path(parent_path, elem, occurrence_index):
    tag = local_tag(elem.tag)
    cls = elem_key_attr(elem)
    seg = f"{tag}[@class='{cls}']" if cls else tag
    if occurrence_index > 1:
        seg += f"[{occurrence_index}]"
    return f"{parent_path}/{seg}" if parent_path else f"/{seg}"


def occurrence_indices(children):
    """Ovoru child kum, adhoda (tag,class) combination edhavadhu ethavadhu
    'nth' occurrence nu oru list return pannum (1-based)."""
    counts = {}
    result = []
    for c in children:
        key = (local_tag(c.tag), elem_key_attr(c))
        counts[key] = counts.get(key, 0) + 1
        result.append(counts[key])
    return result


def compare_attributes(path, before_elem, after_elem):
    b_attrs = dict(before_elem.attrib) if before_elem is not None else {}
    a_attrs = dict(after_elem.attrib) if after_elem is not None else {}

    for k in IGNORE_ATTRIBUTES:
        b_attrs.pop(k, None)
        a_attrs.pop(k, None)

    bl, al = bline(before_elem), aline(after_elem)

    all_keys = sorted(set(b_attrs.keys()) | set(a_attrs.keys()))
    for k in all_keys:
        bv = b_attrs.get(k, None)
        av = a_attrs.get(k, None)
        if bv == av:
            continue
        if bv is None:
            ROWS.append(DiffRow(path, "Attribute Added", "", f"{k} = {av}", bl, al))
        elif av is None:
            ROWS.append(DiffRow(path, "Attribute Removed", f"{k} = {bv}", "", bl, al))
        else:
            ROWS.append(DiffRow(path, "Attribute Modified", f"{k} = {bv}", f"{k} = {av}", bl, al))


def compare_text(path, before_elem, after_elem, kind="Text"):
    bt = before_elem.text if before_elem is not None else None
    at = after_elem.text if after_elem is not None else None
    if IGNORE_WHITESPACE_ONLY_DIFF:
        if norm(bt) == norm(at):
            return
    else:
        if (bt or "") == (at or ""):
            return
    ROWS.append(DiffRow(path, f"{kind} Modified", norm(bt), norm(at), bline(before_elem), aline(after_elem)))


def compare_tail(path, before_elem, after_elem):
    bt = before_elem.tail if before_elem is not None else None
    at = after_elem.tail if after_elem is not None else None
    if norm(bt) == norm(at):
        return
    ROWS.append(DiffRow(path, "Trailing Text Modified", norm(bt), norm(at), bline(before_elem), aline(after_elem)))


def record_added_subtree(path, elem):
    ROWS.append(DiffRow(path, "Element Added", "", short_desc(elem), None, aline(elem)))


def record_removed_subtree(path, elem):
    ROWS.append(DiffRow(path, "Element Removed", short_desc(elem), "", bline(elem), None))


def diff_children(parent_path, before_elem, after_elem):
    b_children = list(before_elem) if before_elem is not None else []
    a_children = list(after_elem) if after_elem is not None else []

    b_sig = [elem_signature(c) for c in b_children]
    a_sig = [elem_signature(c) for c in a_children]

    sm = difflib.SequenceMatcher(None, b_sig, a_sig, autojunk=False)
    opcodes = sm.get_opcodes()

    b_occ = occurrence_indices(b_children)
    a_occ = occurrence_indices(a_children)

    for tag_op, i1, i2, j1, j2 in opcodes:
        if tag_op == "equal":
            for bi, aj in zip(range(i1, i2), range(j1, j2)):
                bpath = build_path(parent_path, b_children[bi], b_occ[bi])
                apath = build_path(parent_path, a_children[aj], a_occ[aj])
                compare_element(apath, b_children[bi], a_children[aj])
        else:
            # replace / delete / insert block -> try a *loose* second-pass
            # match (tag+class only, ignore text) so real "modifications"
            # get paired up instead of being reported as pure add+remove.
            b_block = b_children[i1:i2]
            a_block = a_children[j1:j2]
            b_block_idx = list(range(i1, i2))
            a_block_idx = list(range(j1, j2))

            b_loose = [elem_signature_loose(c) for c in b_block]
            a_loose = [elem_signature_loose(c) for c in a_block]
            sm2 = difflib.SequenceMatcher(None, b_loose, a_loose, autojunk=False)

            for tag2, bi1, bi2, aj1, aj2 in sm2.get_opcodes():
                if tag2 == "equal":
                    for bk, ak in zip(range(bi1, bi2), range(aj1, aj2)):
                        bi = b_block_idx[bk]
                        aj = a_block_idx[ak]
                        apath = build_path(parent_path, a_children[aj], a_occ[aj])
                        compare_element(apath, b_children[bi], a_children[aj])
                elif tag2 == "replace":
                    # pair them up 1:1 as far as possible = "modified"
                    n = min(bi2 - bi1, aj2 - aj1)
                    for k in range(n):
                        bi = b_block_idx[bi1 + k]
                        aj = a_block_idx[aj1 + k]
                        apath = build_path(parent_path, a_children[aj], a_occ[aj])
                        compare_element(apath, b_children[bi], a_children[aj])
                    for k in range(n, bi2 - bi1):
                        bi = b_block_idx[bi1 + k]
                        bpath = build_path(parent_path, b_children[bi], b_occ[bi])
                        record_removed_subtree(bpath, b_children[bi])
                    for k in range(n, aj2 - aj1):
                        aj = a_block_idx[aj1 + k]
                        apath = build_path(parent_path, a_children[aj], a_occ[aj])
                        record_added_subtree(apath, a_children[aj])
                elif tag2 == "delete":
                    for bk in range(bi1, bi2):
                        bi = b_block_idx[bk]
                        bpath = build_path(parent_path, b_children[bi], b_occ[bi])
                        record_removed_subtree(bpath, b_children[bi])
                elif tag2 == "insert":
                    for ak in range(aj1, aj2):
                        aj = a_block_idx[ak]
                        apath = build_path(parent_path, a_children[aj], a_occ[aj])
                        record_added_subtree(apath, a_children[aj])


def compare_element(path, before_elem, after_elem):
    compare_attributes(path, before_elem, after_elem)
    compare_text(path, before_elem, after_elem, kind="Text")
    compare_tail(path, before_elem, after_elem)
    diff_children(path, before_elem, after_elem)


def run_compare(before_path, after_path):
    ROWS.clear()
    BEFORE_LINE_MAP.clear()
    AFTER_LINE_MAP.clear()

    before_tree, b_lines = parse_with_line_numbers(before_path)
    after_tree, a_lines = parse_with_line_numbers(after_path)
    BEFORE_LINE_MAP.update(b_lines)
    AFTER_LINE_MAP.update(a_lines)

    before_root = before_tree.getroot()
    after_root = after_tree.getroot()

    root_path = f"/{local_tag(after_root.tag)}"
    if local_tag(before_root.tag) != local_tag(after_root.tag):
        ROWS.append(DiffRow(root_path, "Root Tag Modified",
                             local_tag(before_root.tag), local_tag(after_root.tag),
                             bline(before_root), aline(after_root)))

    compare_element(root_path, before_root, after_root)
    return ROWS


# Colour used per Change Type - shared by the Excel report AND the
# standalone HTML report, so both downloads look consistent.
CHANGE_TYPE_FILL = {
    "Element Added": "C6EFCE",
    "Element Removed": "FFC7CE",
    "Attribute Added": "DDEBF7",
    "Attribute Removed": "FCE4D6",
    "Attribute Modified": "FFF2CC",
    "Text Modified": "FFF2CC",
    "Trailing Text Modified": "FFF2CC",
    "Root Tag Modified": "FFC7CE",
}
CHANGE_TYPE_TEXT = {
    "Element Added": "006100",
    "Element Removed": "9C0006",
    "Attribute Added": "1F4E78",
    "Attribute Removed": "974706",
    "Attribute Modified": "7F6000",
    "Text Modified": "7F6000",
    "Trailing Text Modified": "7F6000",
    "Root Tag Modified": "9C0006",
}

# Change types where "before" and "after" are two versions of similar
# text (not a pure add/remove) - these get word-level diff highlighting
# instead of a plain flat colour, so only the part that actually changed
# is highlighted (e.g. "Rylander P.N." -> "P.N. Rylander" highlights just
# the reordered name).
MODIFIED_CHANGE_TYPES = {"Text Modified", "Trailing Text Modified", "Attribute Modified"}

WORD_DIFF_DEL_COLOR = "C0392B"   # dark red text, used with a red-ish fill
WORD_DIFF_INS_COLOR = "1E7B34"   # dark green text, used with a green-ish fill
WORD_DIFF_DEL_FILL = "F8B4B0"
WORD_DIFF_INS_FILL = "A8E6B5"


def _tokenize_for_word_diff(s):
    return re.findall(r"\s+|\S+", s or "")


def word_diff_parts(before_str, after_str):
    """Word-level diff between two similar strings.

    Returns (before_parts, after_parts) where each is a list of
    (text, changed) tuples - changed=True for the exact words that
    differ, so callers can highlight ONLY those words instead of the
    whole value.
    """
    a = _tokenize_for_word_diff(before_str)
    b = _tokenize_for_word_diff(after_str)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    before_parts, after_parts = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            text = "".join(a[i1:i2])
            before_parts.append((text, False))
            after_parts.append((text, False))
        else:
            if i2 > i1:
                before_parts.append(("".join(a[i1:i2]), True))
            if j2 > j1:
                after_parts.append(("".join(b[j1:j2]), True))
    return before_parts, after_parts


def word_diff_html(before_str, after_str):
    """Same as word_diff_parts(), but rendered as highlighted HTML spans
    for the standalone HTML report."""
    before_parts, after_parts = word_diff_parts(before_str, after_str)
    before_html = "".join(
        f'<span class="worddiff-del">{html.escape(t)}</span>' if changed else html.escape(t)
        for t, changed in before_parts
    )
    after_html = "".join(
        f'<span class="worddiff-ins">{html.escape(t)}</span>' if changed else html.escape(t)
        for t, changed in after_parts
    )
    return before_html, after_html


def word_diff_rich_text(parts, changed_color):
    """Turns word_diff_parts() output into an openpyxl CellRichText value
    so the Excel cell shows multiple colours in a single cell - only the
    changed word(s) get coloured/bold, the rest stays plain black text."""
    blocks = []
    for text, changed in parts:
        if not text:
            continue
        if changed:
            blocks.append(TextBlock(InlineFont(color=changed_color, b=True), text))
        else:
            blocks.append(text)
    if not blocks:
        return ""
    return CellRichText(*blocks)


def write_excel(rows, output_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "XML Compare Report"

    headers = ["S.No", "Before Line No", "After Line No", "XML Location (Path)",
               "Change Type", "Before Value", "After Value"]
    ws.append(headers)

    header_fill = PatternFill(start_color="305496", end_color="305496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for idx, row in enumerate(rows, start=1):
        ws.append([idx, row.before_line, row.after_line, row.path,
                   row.change_type, row.before, row.after])

        if row.change_type in MODIFIED_CHANGE_TYPES and row.before and row.after:
            # Word-level highlight: only the EXACT word(s) that changed
            # get coloured (red strike = removed, green bold = added)
            # inside the Before/After Value cells, instead of flat-
            # colouring the whole row.
            before_parts, after_parts = word_diff_parts(row.before, row.after)
            before_cell = ws.cell(row=idx + 1, column=6)
            after_cell = ws.cell(row=idx + 1, column=7)
            before_rt = word_diff_rich_text(before_parts, WORD_DIFF_DEL_COLOR)
            after_rt = word_diff_rich_text(after_parts, WORD_DIFF_INS_COLOR)
            if before_rt:
                before_cell.value = before_rt
            if after_rt:
                after_cell.value = after_rt
            # Faint neutral tint on the rest of the row so the mistake
            # is still easy to spot in the sheet.
            neutral_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
            for col in (1, 2, 3, 4, 5):
                ws.cell(row=idx + 1, column=col).fill = neutral_fill
        else:
            fill_color = CHANGE_TYPE_FILL.get(row.change_type)
            text_color = CHANGE_TYPE_TEXT.get(row.change_type)
            if fill_color:
                # Highlight the WHOLE mistake row (all 7 columns), not
                # just the Change Type cell, so each row is easy to scan
                # at a glance.
                row_fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
                row_font = Font(color=text_color) if text_color else None
                for col in range(1, len(headers) + 1):
                    cell = ws.cell(row=idx + 1, column=col)
                    cell.fill = row_fill
                    if row_font:
                        cell.font = row_font

        for col in (1, 2, 3):
            ws.cell(row=idx + 1, column=col).alignment = Alignment(horizontal="center")

    widths = [8, 14, 14, 65, 22, 50, 50]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:G{len(rows) + 1}"

    wb.save(output_path)


def write_html_report(rows, output_path, before_path, after_path):
    """Standalone, colour-coded HTML mistake report - same rows as the
    Excel report, but as a single .html file that opens in any browser,
    with no Excel/library needed to view it. Colours match write_excel()
    (see CHANGE_TYPE_FILL / CHANGE_TYPE_TEXT above)."""

    def esc(v):
        return html.escape(str(v)) if v not in (None, "") else ""

    added = sum(1 for r in rows if r.change_type == "Element Added")
    removed = sum(1 for r in rows if r.change_type == "Element Removed")
    attr_changes = sum(1 for r in rows if r.change_type.startswith("Attribute"))
    text_changes = sum(1 for r in rows if "Text" in r.change_type)

    rows_html = []
    for idx, row in enumerate(rows, start=1):
        css_class = "ct-" + row.change_type.replace(" ", "-").lower()
        if row.change_type in MODIFIED_CHANGE_TYPES and row.before and row.after:
            before_cell, after_cell = word_diff_html(row.before, row.after)
        else:
            before_cell = esc(row.before) or '<span class="muted">&mdash;</span>'
            after_cell = esc(row.after) or '<span class="muted">&mdash;</span>'
        rows_html.append(f"""<tr class="{css_class}">
        <td class="num">{idx}</td>
        <td class="num">{row.before_line if row.before_line else '&mdash;'}</td>
        <td class="num">{row.after_line if row.after_line else '&mdash;'}</td>
        <td class="path">{esc(row.path)}</td>
        <td class="type"><span class="badge">{esc(row.change_type)}</span></td>
        <td class="val">{before_cell}</td>
        <td class="val">{after_cell}</td>
      </tr>""")
    rows_html_str = "\n".join(rows_html) if rows_html else \
        '<tr><td colspan="7" style="text-align:center;padding:20px;color:#9aa0ab">No differences found.</td></tr>'

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>XML Mistake Report</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; background:#f4f5f7; color:#1f2430; margin:0; padding:24px; }}
  h1 {{ font-size:18px; margin:0 0 4px 0; }}
  .meta {{ font-size:12px; color:#6b7280; margin-bottom:16px; }}
  .files {{ font-size:12px; color:#6b7280; margin-bottom:16px; }}
  .stats {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:18px; }}
  .stat {{ background:#fff; border:1px solid #e2e4e9; border-radius:8px; padding:8px 14px; font-size:12.5px; }}
  .stat b {{ font-size:15px; display:block; }}
  table {{ border-collapse:collapse; width:100%; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.08); }}
  thead th {{ background:#1f2a44; color:#fff; text-align:left; padding:8px 10px; font-size:12px; position:sticky; top:0; }}
  td {{ padding:7px 10px; font-size:12.5px; border-bottom:1px solid #eceef2; vertical-align:top; word-break:break-word; }}
  td.num {{ text-align:center; color:#6b7280; width:70px; }}
  td.path {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size:11.5px; color:#334; width:22%; }}
  td.type {{ width:150px; }}
  .badge {{ display:inline-block; font-size:10.5px; font-weight:700; padding:2px 8px; border-radius:10px; background:rgba(0,0,0,0.08); }}
  .muted {{ color:#a0a4ad; }}
  tr.ct-element-added        {{ background:#e6f6ea; }}
  tr.ct-element-removed      {{ background:#fde3e2; }}
  tr.ct-attribute-added      {{ background:#e7f1fb; }}
  tr.ct-attribute-removed    {{ background:#fdece0; }}
  tr.ct-attribute-modified   {{ background:#fff8df; }}
  tr.ct-text-modified        {{ background:#fff8df; }}
  tr.ct-trailing-text-modified {{ background:#fff8df; }}
  tr.ct-root-tag-modified    {{ background:#fde3e2; }}
  tr.ct-element-added .badge      {{ background:#c6efce; color:#006100; }}
  tr.ct-element-removed .badge    {{ background:#ffc7ce; color:#9c0006; }}
  tr.ct-attribute-added .badge    {{ background:#ddebf7; color:#1f4e78; }}
  tr.ct-attribute-removed .badge  {{ background:#fce4d6; color:#974706; }}
  tr.ct-attribute-modified .badge,
  tr.ct-text-modified .badge,
  tr.ct-trailing-text-modified .badge {{ background:#fff2cc; color:#7f6000; }}
  tr.ct-root-tag-modified .badge  {{ background:#ffc7ce; color:#9c0006; }}
  .legend {{ display:flex; gap:14px; flex-wrap:wrap; font-size:11.5px; margin-bottom:14px; }}
  .legend span {{ display:inline-flex; align-items:center; gap:5px; }}
  .legend i {{ width:11px; height:11px; border-radius:3px; display:inline-block; }}
  .worddiff-del {{ background:#f8b4b0; text-decoration:line-through; padding:0 2px; border-radius:2px; }}
  .worddiff-ins {{ background:#a8e6b5; padding:0 2px; border-radius:2px; }}
</style>
</head>
<body>
  <h1>XML Mistake Report</h1>
  <div class="meta">Generated {stamp}</div>
  <div class="files">Before: <b>{esc(before_path)}</b> &nbsp;|&nbsp; After: <b>{esc(after_path)}</b></div>
  <div class="stats">
    <div class="stat"><b>{len(rows)}</b>Total mistakes</div>
    <div class="stat"><b>{added}</b>Elements added</div>
    <div class="stat"><b>{removed}</b>Elements removed</div>
    <div class="stat"><b>{attr_changes}</b>Attribute changes</div>
    <div class="stat"><b>{text_changes}</b>Text changes</div>
  </div>
  <div class="legend">
    <span><i style="background:#c6efce"></i>Added</span>
    <span><i style="background:#ffc7ce"></i>Removed</span>
    <span><i style="background:#ddebf7"></i>Attribute Added</span>
    <span><i style="background:#fce4d6"></i>Attribute Removed</span>
    <span><i style="background:#fff2cc"></i>Modified row</span>
    <span><i style="background:#a8e6b5"></i>Exact word added</span>
    <span><i style="background:#f8b4b0"></i>Exact word removed</span>
  </div>
  <table>
    <thead>
      <tr>
        <th>S.No</th><th>Before Line</th><th>After Line</th><th>XML Path</th>
        <th>Change Type</th><th>Before Value</th><th>After Value</th>
      </tr>
    </thead>
    <tbody>
      {rows_html_str}
    </tbody>
  </table>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_doc)


def annotate_file(original_path, output_path, rows, line_attr):
    """Original XML file ah copy pannitu, ovoru diff irukura line mela
    '<!-- >>> CHANGE #S.No ... -->' comment insert pannum. Original file
    edhuvum edit aagathu - puthu separate file thaan create aagum."""
    with open(original_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # line number -> list of (sno, change_type)
    marks = {}
    for sno, row in enumerate(rows, start=1):
        ln = getattr(row, line_attr)
        if ln:
            marks.setdefault(ln, []).append((sno, row.change_type))

    new_lines = []
    for i, line in enumerate(lines, start=1):
        if i in marks:
            indent_match = re.match(r"^[ \t]*", line)
            indent = indent_match.group(0) if indent_match else ""
            parts = "; ".join(f"#{sno} {ctype}" for sno, ctype in marks[i])
            comment = f"{indent}<!-- >>> CHANGE {parts} >>> -->\n"
            new_lines.append(comment)
        new_lines.append(line)

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


if __name__ == "__main__":
    print(f"Comparing:\n  BEFORE: {BEFORE_XML_PATH}\n  AFTER : {AFTER_XML_PATH}")
    result_rows = run_compare(BEFORE_XML_PATH, AFTER_XML_PATH)
    write_excel(result_rows, OUTPUT_EXCEL_PATH)
    print(f"Done. {len(result_rows)} difference(s) found.")
    print(f"Excel report saved to: {OUTPUT_EXCEL_PATH}")

    if OUTPUT_HTML_PATH:
        write_html_report(result_rows, OUTPUT_HTML_PATH, BEFORE_XML_PATH, AFTER_XML_PATH)
        print(f"HTML mistake report saved to: {OUTPUT_HTML_PATH}")

    if GENERATE_ANNOTATED_COPIES:
        annotate_file(BEFORE_XML_PATH, ANNOTATED_BEFORE_PATH, result_rows, "before_line")
        annotate_file(AFTER_XML_PATH, ANNOTATED_AFTER_PATH, result_rows, "after_line")
        print(f"Annotated BEFORE file: {ANNOTATED_BEFORE_PATH}")
        print(f"Annotated AFTER file : {ANNOTATED_AFTER_PATH}")
