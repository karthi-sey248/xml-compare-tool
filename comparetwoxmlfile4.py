import os
import re
import html
from difflib import SequenceMatcher
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SOURCE_FILE = BASE_DIR / r"\\192.168.60.5\Public\Karthikeyan AI\Conversion\004a\PG2QL\tx2.xml"
CONVERTED_FILE = BASE_DIR / r"\\192.168.60.5\Public\Karthikeyan AI\Conversion\004a\FM_ML\tx2.xml"

SOURCE_CLEANED = BASE_DIR / r"\\192.168.60.5\Public\Karthikeyan AI\Conversion\004a\source_cleaned.html"
CONVERTED_CLEANED = BASE_DIR / r"\\192.168.60.5\Public\Karthikeyan AI\Conversion\004a\converted_cleaned.html"

MAIN_REPORT = BASE_DIR / r"\\192.168.60.5\Public\Karthikeyan AI\Conversion\004a\content_comparison_report1.html"
DETAIL_REPORT = BASE_DIR / r"\\192.168.60.5\Public\Karthikeyan AI\Conversion\004a\content_mistake_detail1.html"

# Number of meaningful tokens around the mistake
CONTEXT_TOKENS = 12


# ============================================================
# HELPERS
# ============================================================

def normalize_text(text):
    """
    Normalize text only for comparison.

    Important:
    Original text is preserved in token metadata.
    """
    if not text:
        return ""

    text = html.unescape(text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Space around punctuation
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([(\[{])\s+", r"\1", text)
    text = re.sub(r"\s+([)\]}])", r"\1", text)

    # Common missing-space situations
    text = re.sub(r"(\d)\.([A-Za-z])", r"\1. \2", text)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)

    return text.strip()


def tokenize_text(text):
    """
    Keep words and punctuation separately.
    """
    return re.findall(r"\w+(?:[-'][\w]+)*|[^\w\s]", text, re.UNICODE)


def escape(value):
    return html.escape(str(value), quote=False)


# ============================================================
# RAW HTML/XML PARSER
# ============================================================

TAG_PATTERN = re.compile(
    r"<!--.*?-->"
    r"|<!\[CDATA\[.*?\]\]>"
    r"|<[^>]+>"
    r"|[^<]+",
    re.DOTALL
)

# ------------------------------------------------------------
# HTML "void" elements.
#
# These tags NEVER have a closing tag in real-world HTML
# (Plain_Html.html especially, since it is usually exported
# from Word/PDF and rarely self-closes tags like <br>, <img>,
# <meta>, <link>, <hr> ...).
#
# If a void tag is mistakenly pushed onto the tag stack (because
# it wasn't written as <br/> with a slash), it will NEVER be
# popped back off. Every single tag/parent-path reported for the
# rest of the document after that point becomes wrong, which is
# exactly the "tag details incorrect" problem in the detail
# report. So these tags are always treated as self-closing,
# regardless of whether the author wrote a trailing "/".
# ------------------------------------------------------------
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
}

# ------------------------------------------------------------
# HTML elements with "optional" closing tags.
#
# Real-world HTML frequently omits the closing tag for these
# (e.g. a new <p> or <li> starts without the previous one ever
# being closed). If we don't account for this, the old
# unclosed tag stays on the stack forever and swallows every
# following tag as a "child", corrupting the parent path and
# exact-tag info for the rest of the document.
#
# When a new tag from this set is opened and the current
# innermost open tag on the stack has the SAME name, we
# implicitly close (pop) the old one first.
# ------------------------------------------------------------
AUTO_CLOSE_SIBLINGS = {
    "p", "li", "tr", "td", "th", "option", "dd", "dt",
    "thead", "tbody", "tfoot"
}


def parse_raw_file(file_path):
    """
    Parse source XML/HTML without destroying original line information.

    For every text chunk we store:
        text
        line
        exact containing tag
        full opening tag
        tag stack
        parent path

    The top/innermost tag is treated as the exact tag
    containing the changed content.
    """

    content = file_path.read_text(
        encoding="utf-8",
        errors="replace"
    )

    records = []

    tag_stack = []

    # Track source position
    current_line = 1

    for match in TAG_PATTERN.finditer(content):
        piece = match.group(0)

        if not piece:
            continue

        piece_line = current_line

        if piece.startswith("<"):
            # ------------------------------------------------
            # Comment / CDATA
            # ------------------------------------------------
            if piece.startswith("<!--"):
                current_line += piece.count("\n")
                continue

            if piece.startswith("<![CDATA["):
                cdata_text = re.sub(
                    r"<!\[CDATA\[(.*?)\]\]>",
                    r"\1",
                    piece,
                    flags=re.DOTALL
                )

                if cdata_text.strip() and tag_stack:
                    records.append({
                        "text": cdata_text,
                        "line": piece_line,
                        "tag": tag_stack[-1]["name"],
                        "full_tag": tag_stack[-1]["full_tag"],
                        "tag_open_line": tag_stack[-1]["line"],
                        "stack": [x["name"] for x in tag_stack],
                        "parent_path": " > ".join(
                            x["name"] for x in tag_stack
                        )
                    })

                current_line += piece.count("\n")
                continue

            # ------------------------------------------------
            # Closing tag
            # ------------------------------------------------
            close_match = re.match(
                r"<\s*/\s*([^\s>]+)",
                piece
            )

            if close_match:
                close_name = close_match.group(1)
                close_name_lower = close_name.lower()

                # Pop until matching tag is found.
                # Matched case-insensitively because HTML tag
                # names are case-insensitive (<DIV>...</div> is
                # perfectly valid HTML). Matching case-sensitively
                # here would leave the opening tag on the stack
                # forever, corrupting every tag reported after it.
                for i in range(len(tag_stack) - 1, -1, -1):
                    if tag_stack[i]["name_lower"] == close_name_lower:
                        tag_stack = tag_stack[:i]
                        break
                else:
                    # No matching opening tag anywhere on the
                    # stack. This is a stray/unmatched closing
                    # tag - ignore it instead of silently
                    # corrupting the stack.
                    pass

                current_line += piece.count("\n")
                continue

            # ------------------------------------------------
            # XML declaration / DOCTYPE / processing instruction
            # ------------------------------------------------
            if (
                piece.startswith("<?")
                or piece.startswith("<!")
            ):
                current_line += piece.count("\n")
                continue

            # ------------------------------------------------
            # Opening / self-closing tag
            # ------------------------------------------------
            open_match = re.match(
                r"<\s*([^\s/>]+)",
                piece
            )

            if open_match:
                tag_name = open_match.group(1)
                tag_name_lower = tag_name.lower()

                is_self_closing = (
                    bool(re.search(r"/\s*>$", piece))
                    # Always treat known HTML void elements as
                    # self-closing, even without a trailing "/",
                    # since real Plain_Html.html files almost
                    # never write <br/>, <img/>, <meta/> etc.
                    # with the slash. Missing this is what makes
                    # the tag stack (and therefore every tag/path
                    # reported afterwards) drift and go wrong.
                    or tag_name_lower in VOID_ELEMENTS
                )

                # Optional-closing-tag elements (<p>, <li>,
                # <tr>, <td>, ...): a new one silently closes a
                # previous sibling of the same name instead of
                # nesting inside it.
                if (
                    not is_self_closing
                    and tag_name_lower in AUTO_CLOSE_SIBLINGS
                    and tag_stack
                    and tag_stack[-1]["name_lower"] == tag_name_lower
                ):
                    tag_stack = tag_stack[:-1]

                tag_info = {
                    "name": tag_name,
                    "name_lower": tag_name_lower,
                    "full_tag": piece.strip(),
                    "line": piece_line
                }

                if not is_self_closing:
                    tag_stack.append(tag_info)

            current_line += piece.count("\n")
            continue

        # ====================================================
        # TEXT CHUNK
        # ====================================================

        if not tag_stack:
            current_line += piece.count("\n")
            continue

        if not piece.strip():
            current_line += piece.count("\n")
            continue

        # Split multiline text while preserving exact line
        # where each part starts.
        parts = piece.splitlines(keepends=True)

        line = piece_line

        for part in parts:

            clean_part = part.strip()

            if clean_part:
                records.append({
                    "text": clean_part,
                    "line": line,
                    "tag": tag_stack[-1]["name"],
                    "full_tag": tag_stack[-1]["full_tag"],
                    "tag_open_line": tag_stack[-1]["line"],
                    "stack": [x["name"] for x in tag_stack],
                    "parent_path": " > ".join(
                        x["name"] for x in tag_stack
                    )
                })

            line += part.count("\n")

        current_line += piece.count("\n")

    return records


# ============================================================
# BUILD COMPARISON TOKENS
# ============================================================

def build_tokens(records):
    """
    Convert text records into comparison tokens while retaining
    exact source metadata.

    Each token contains:
        comparison text
        original text
        line
        exact tag
        full tag
        parent path
    """

    tokens = []

    for record_index, record in enumerate(records):

        original_text = html.unescape(record["text"])

        normalized = normalize_text(original_text)

        if not normalized:
            continue

        words = tokenize_text(normalized)

        for word in words:

            tokens.append({
                "text": word,
                "original_text": word,
                "record_index": record_index,

                "line": record["line"],
                "tag": record["tag"],
                "full_tag": record["full_tag"],
                "tag_open_line": record["tag_open_line"],

                "stack": record["stack"],
                "parent_path": record["parent_path"]
            })

    return tokens


# ============================================================
# CLEANED FILE GENERATION
# ============================================================

def generate_cleaned_file(input_file, output_file):
    """
    Remove every tag except <b> and <i>.
    Text content is retained.

    Example:

        <div>Hello <span>world</span></div>

    becomes:

        Hello world

    While:

        <div><b>Hello</b> <i>world</i></div>

    becomes:

        <b>Hello</b> <i>world</i>
    """

    content = input_file.read_text(
        encoding="utf-8",
        errors="replace"
    )

    # Remove comments
    content = re.sub(
        r"<!--.*?-->",
        "",
        content,
        flags=re.DOTALL
    )

    # Keep only b/i tags
    def replace_tag(match):
        tag = match.group(0)

        name_match = re.match(
            r"<\s*/?\s*([^\s/>]+)",
            tag
        )

        if not name_match:
            return ""

        name = name_match.group(1).lower()

        if name in ("b", "i"):
            return tag

        return ""

    cleaned = re.sub(
        r"<[^>]+>",
        replace_tag,
        content,
        flags=re.DOTALL
    )

    # Normalize excessive blank lines but preserve useful
    # line structure.
    cleaned = re.sub(
        r"\n[ \t]*\n[ \t]*\n+",
        "\n\n",
        cleaned
    )

    output_file.write_text(
        cleaned,
        encoding="utf-8"
    )


# ============================================================
# CONTEXT EXTRACTION
# ============================================================

def get_record_range(tokens, start_index, end_index):
    """
    Get record indexes involved in a difference.
    """

    if not tokens:
        return []

    indexes = []

    start_index = max(0, start_index)
    end_index = min(len(tokens) - 1, end_index)

    for i in range(start_index, end_index + 1):
        idx = tokens[i]["record_index"]
        if idx not in indexes:
            indexes.append(idx)

    return indexes


def build_context(tokens, start_index, end_index):
    """
    Build meaningful context around the difference.

    It does NOT dump random ±2 lines.

    Instead:
      - starts around the detected difference
      - includes meaningful nearby tokens
      - preserves exact tag information
      - groups tokens belonging to the same tag
    """

    if not tokens:
        return {
            "html": "",
            "plain": "",
            "records": []
        }

    center = (start_index + end_index) // 2

    left = max(
        0,
        center - CONTEXT_TOKENS
    )

    right = min(
        len(tokens),
        center + CONTEXT_TOKENS + 1
    )

    selected = tokens[left:right]

    # Group tokens by record
    grouped = []

    current_record = None
    current_tokens = []

    for token in selected:

        record_id = token["record_index"]

        if current_record is None:
            current_record = record_id

        if record_id != current_record:

            grouped.append(
                (current_record, current_tokens)
            )

            current_record = record_id
            current_tokens = []

        current_tokens.append(token)

    if current_tokens:
        grouped.append(
            (current_record, current_tokens)
        )

    return {
        "tokens": selected,
        "groups": grouped
    }


# ============================================================
# HTML CONTEXT RENDERING
# ============================================================

def render_context(
    tokens,
    highlight_start=None,
    highlight_end=None,
    highlight_type="removed"
):
    """
    Render contextual text.

    Red:
        Source removed/changed

    Green:
        Converted added/changed
    """

    if not tokens:
        return ""

    output = []

    for index, token in enumerate(tokens):

        text_value = escape(token["original_text"])

        if (
            highlight_start is not None
            and highlight_start <= index <= highlight_end
        ):

            css_class = (
                "removed"
                if highlight_type == "removed"
                else "added"
            )

            text_value = (
                f'<span class="{css_class}">'
                f'{text_value}'
                f'</span>'
            )

        output.append(text_value)

    # Smart spacing
    result = ""

    previous = None

    for value, token in zip(output, tokens):

        raw = token["original_text"]

        if previous is None:
            result += value

        elif raw in ".,;:!?)]}":
            result += value

        elif previous in "([{":
            result += value

        else:
            result += " " + value

        previous = raw

    return result


# ============================================================
# DIFFERENCE CLASSIFICATION
# ============================================================

def compare_tokens(source_tokens, converted_tokens):
    """
    SequenceMatcher comparison.

    Returns detailed change records.
    """

    source_seq = [
        token["text"]
        for token in source_tokens
    ]

    converted_seq = [
        token["text"]
        for token in converted_tokens
    ]

    matcher = SequenceMatcher(
        None,
        source_seq,
        converted_seq,
        autojunk=False
    )

    changes = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag == "equal":
            continue

        source_part = source_tokens[i1:i2]
        converted_part = converted_tokens[j1:j2]

        if tag == "delete":
            change_type = "Removed"

        elif tag == "insert":
            change_type = "Added"

        elif tag == "replace":
            change_type = "Changed"

        else:
            change_type = tag.title()

        changes.append({
            "type": change_type,

            "source_start": i1,
            "source_end": i2,

            "converted_start": j1,
            "converted_end": j2,

            "source_tokens": source_part,
            "converted_tokens": converted_part
        })

    return changes


# ============================================================
# EXACT TAG INFORMATION
# ============================================================

def get_exact_tag(tokens):
    """
    Return the exact innermost tag associated with the mistake.

    This intentionally avoids returning parent/sibling tags.
    """

    if not tokens:
        return None

    token = tokens[0]

    return {
        "tag": token["tag"],
        "full_tag": token["full_tag"],
        "line": token["line"],
        "parent_path": token["parent_path"]
    }


def get_tag_summary(tokens):
    """
    If multiple changed tokens belong to the same exact tag,
    show one tag.

    If multiple tags are genuinely involved, show each
    relevant exact tag only.
    """

    if not tokens:
        return []

    result = []

    seen = set()

    for token in tokens:

        key = (
            token["tag"],
            token["full_tag"],
            token["line"]
        )

        if key in seen:
            continue

        seen.add(key)

        result.append({
            "tag": token["tag"],
            "full_tag": token["full_tag"],
            "line": token["line"],
            "parent_path": token["parent_path"]
        })

    return result


# ============================================================
# MAIN REPORT
# ============================================================

def generate_main_report(changes, source_tokens, converted_tokens):

    rows = []

    for number, change in enumerate(changes, start=1):

        source_part = change["source_tokens"]
        converted_part = change["converted_tokens"]

        source_start = change["source_start"]
        source_end = change["source_end"]

        converted_start = change["converted_start"]
        converted_end = change["converted_end"]

        # ----------------------------------------------------
        # Source context
        # ----------------------------------------------------

        if source_part:

            source_context_data = build_context(
                source_tokens,
                source_start,
                max(
                    source_start,
                    source_end - 1
                )
            )

            source_context_tokens = source_context_data["tokens"]

            # Find highlight position inside context
            source_offset = max(
                0,
                source_start -
                max(0, source_start - CONTEXT_TOKENS)
            )

            source_highlight_end = (
                source_offset +
                len(source_part) - 1
            )

            source_context = render_context(
                source_context_tokens,
                source_offset,
                source_highlight_end,
                "removed"
            )

            source_line = source_part[0]["line"]

        else:

            source_context = "Not Found"
            source_line = "—"

        # ----------------------------------------------------
        # Converted context
        # ----------------------------------------------------

        if converted_part:

            converted_context_data = build_context(
                converted_tokens,
                converted_start,
                max(
                    converted_start,
                    converted_end - 1
                )
            )

            converted_context_tokens = (
                converted_context_data["tokens"]
            )

            converted_offset = max(
                0,
                converted_start -
                max(0, converted_start - CONTEXT_TOKENS)
            )

            converted_highlight_end = (
                converted_offset +
                len(converted_part) - 1
            )

            converted_context = render_context(
                converted_context_tokens,
                converted_offset,
                converted_highlight_end,
                "added"
            )

            converted_line = converted_part[0]["line"]

        else:

            converted_context = "Not Found"
            converted_line = "—"

        rows.append(f"""
        <tr>
            <td>{number}</td>
            <td><b>{escape(change["type"])}</b></td>
            <td>{escape(source_line)}</td>
            <td>{escape(converted_line)}</td>

            <td class="context source-context">
                {source_context}
            </td>

            <td class="context converted-context">
                {converted_context}
            </td>
        </tr>
        """)

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">

<title>XML Content Comparison Report</title>

<style>

body {{
    font-family: Arial, sans-serif;
    margin: 30px;
    background: #f7f7f7;
}}

h1 {{
    margin-bottom: 5px;
}}

.summary {{
    margin-bottom: 20px;
    padding: 15px;
    background: white;
    border: 1px solid #ddd;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    background: white;
}}

th {{
    background: #333;
    color: white;
    padding: 10px;
    text-align: left;
}}

td {{
    border: 1px solid #ddd;
    padding: 10px;
    vertical-align: top;
}}

.context {{
    line-height: 1.7;
    font-family: Consolas, monospace;
}}

.source-context {{
    background: #fffafa;
}}

.converted-context {{
    background: #fafffa;
}}

.removed {{
    background: #ffb3b3;
    color: #900;
    font-weight: bold;
    padding: 2px 4px;
}}

.added {{
    background: #b9f6b9;
    color: #075f07;
    font-weight: bold;
    padding: 2px 4px;
}}

tr:hover {{
    background: #f1f1f1;
}}

.legend {{
    margin: 15px 0;
}}

.legend span {{
    padding: 5px 10px;
    margin-right: 10px;
}}

.legend-red {{
    background: #ffb3b3;
}}

.legend-green {{
    background: #b9f6b9;
}}

</style>

</head>

<body>

<h1>XML Content Comparison Report</h1>

<div class="summary">

<b>Total Differences:</b>
{len(changes)}

<div class="legend">

<span class="legend-red">
Source Removed / Changed
</span>

<span class="legend-green">
Converted Added / Changed
</span>

</div>

<p>
Only <code>&lt;b&gt;</code> and <code>&lt;i&gt;</code>
formatting tags are retained during comparison.
All other tags are ignored while preserving their text content.
</p>

</div>

<table>

<thead>
<tr>
    <th>#</th>
    <th>Change</th>
    <th>Source Line</th>
    <th>Converted Line</th>
    <th>Source Context</th>
    <th>Converted Context</th>
</tr>
</thead>

<tbody>

{''.join(rows)}

</tbody>

</table>

</body>
</html>
"""

    MAIN_REPORT.write_text(
        html_content,
        encoding="utf-8"
    )


# ============================================================
# DETAILED MISTAKE REPORT
# ============================================================

def generate_detail_report(
    changes,
    source_tokens,
    converted_tokens
):

    cards = []

    for number, change in enumerate(changes, start=1):

        source_part = change["source_tokens"]
        converted_part = change["converted_tokens"]

        # ----------------------------------------------------
        # Exact tag information
        # ----------------------------------------------------

        source_tags = get_tag_summary(
            source_part
        )

        converted_tags = get_tag_summary(
            converted_part
        )

        # ----------------------------------------------------
        # Exact mistake text
        # ----------------------------------------------------

        source_text = " ".join(
            token["original_text"]
            for token in source_part
        )

        converted_text = " ".join(
            token["original_text"]
            for token in converted_part
        )

        # ----------------------------------------------------
        # Exact source location
        # ----------------------------------------------------

        source_line = (
            source_part[0]["line"]
            if source_part
            else "Not Found"
        )

        converted_line = (
            converted_part[0]["line"]
            if converted_part
            else "Not Found"
        )

        # ----------------------------------------------------
        # Arounded context
        # ----------------------------------------------------

        if source_part:

            source_context_data = build_context(
                source_tokens,
                change["source_start"],
                max(
                    change["source_start"],
                    change["source_end"] - 1
                )
            )

            source_context_tokens = (
                source_context_data["tokens"]
            )

            source_base = max(
                0,
                change["source_start"] - CONTEXT_TOKENS
            )

            source_highlight_start = (
                change["source_start"] - source_base
            )

            source_highlight_end = (
                source_highlight_start +
                len(source_part) - 1
            )

            source_context = render_context(
                source_context_tokens,
                source_highlight_start,
                source_highlight_end,
                "removed"
            )

        else:

            source_context = "Not Found"

        if converted_part:

            converted_context_data = build_context(
                converted_tokens,
                change["converted_start"],
                max(
                    change["converted_start"],
                    change["converted_end"] - 1
                )
            )

            converted_context_tokens = (
                converted_context_data["tokens"]
            )

            converted_base = max(
                0,
                change["converted_start"] -
                CONTEXT_TOKENS
            )

            converted_highlight_start = (
                change["converted_start"] -
                converted_base
            )

            converted_highlight_end = (
                converted_highlight_start +
                len(converted_part) - 1
            )

            converted_context = render_context(
                converted_context_tokens,
                converted_highlight_start,
                converted_highlight_end,
                "added"
            )

        else:

            converted_context = "Not Found"

        # ----------------------------------------------------
        # Exact tags
        # ----------------------------------------------------

        def tag_html(tags):

            if not tags:
                return "<span class='not-found'>Not Found</span>"

            output = []

            for tag in tags:

                output.append(
                    f"""
                    <div class="tag-item">
                        <div>
                            <b>Tag:</b>
                            <code>&lt;{escape(tag["tag"])}&gt;</code>
                        </div>

                        <div>
                            <b>Line:</b>
                            {tag["line"]}
                        </div>

                        <div>
                            <b>Opening Tag:</b>
                            <code>{escape(tag["full_tag"])}</code>
                        </div>

                        <div>
                            <b>Path:</b>
                            <code>{escape(tag["parent_path"])}</code>
                        </div>
                    </div>
                    """
                )

            return "".join(output)

        # ----------------------------------------------------
        # Create detailed card
        # ----------------------------------------------------

        cards.append(f"""

<div class="mistake-card">

<div class="mistake-header">

    <div>
        <span class="number">#{number}</span>

        <span class="change-type">
            {escape(change["type"])}
        </span>
    </div>

</div>


<div class="location-grid">

    <div class="location source-location">

        <h3>Source</h3>

        <p>
            <b>Line:</b>
            {escape(source_line)}
        </p>

        <p>
            <b>Exact Mistake:</b>
        </p>

        <div class="exact-text removed-box">
            {escape(source_text) if source_text else "Not Found"}
        </div>

    </div>


    <div class="location converted-location">

        <h3>Converted</h3>

        <p>
            <b>Line:</b>
            {escape(converted_line)}
        </p>

        <p>
            <b>Exact Difference:</b>
        </p>

        <div class="exact-text added-box">
            {escape(converted_text) if converted_text else "Not Found"}
        </div>

    </div>

</div>


<div class="tag-grid">

    <div>

        <h3>Source Exact Tag</h3>

        {tag_html(source_tags)}

    </div>


    <div>

        <h3>Converted Exact Tag</h3>

        {tag_html(converted_tags)}

    </div>

</div>


<div class="context-section">

    <h3>Source Arounded Context</h3>

    <div class="context source-context">
        {source_context}
    </div>

</div>


<div class="context-section">

    <h3>Converted Arounded Context</h3>

    <div class="context converted-context">
        {converted_context}
    </div>

</div>


</div>

""")

    html_content = f"""

<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<title>Detailed XML Content Mistakes</title>

<style>

body {{
    font-family: Arial, sans-serif;
    margin: 30px;
    background: #f4f5f7;
    color: #222;
}}

h1 {{
    margin-bottom: 5px;
}}

.description {{
    background: white;
    padding: 15px;
    border: 1px solid #ddd;
    margin-bottom: 25px;
}}

.mistake-card {{
    background: white;
    border: 1px solid #ccc;
    margin-bottom: 25px;
    padding: 20px;
    border-radius: 6px;
}}

.mistake-header {{
    border-bottom: 1px solid #ddd;
    padding-bottom: 12px;
    margin-bottom: 15px;
}}

.number {{
    font-size: 20px;
    font-weight: bold;
}}

.change-type {{
    margin-left: 15px;
    background: #444;
    color: white;
    padding: 5px 10px;
    border-radius: 4px;
}}

.location-grid,
.tag-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 20px;
}}

.location {{
    padding: 15px;
    border: 1px solid #ddd;
}}

.source-location {{
    background: #fffafa;
}}

.converted-location {{
    background: #fafffa;
}}

.exact-text {{
    padding: 12px;
    font-family: Consolas, monospace;
    font-weight: bold;
    min-height: 20px;
}}

.removed-box {{
    background: #ffb3b3;
    color: #800;
}}

.added-box {{
    background: #b9f6b9;
    color: #075f07;
}}

.tag-item {{
    border: 1px solid #ddd;
    background: #fafafa;
    padding: 12px;
    margin-bottom: 10px;
}}

.tag-item code {{
    font-family: Consolas, monospace;
    word-break: break-word;
}}

.not-found {{
    color: #999;
    font-style: italic;
}}

.context-section {{
    margin-top: 20px;
}}

.context {{
    padding: 15px;
    border: 1px solid #ddd;
    font-family: Consolas, monospace;
    line-height: 1.8;
    white-space: normal;
}}

.source-context {{
    background: #fffafa;
}}

.converted-context {{
    background: #fafffa;
}}

.removed {{
    background: #ff9999;
    color: #700;
    font-weight: bold;
    padding: 2px 5px;
}}

.added {{
    background: #99e699;
    color: #064d06;
    font-weight: bold;
    padding: 2px 5px;
}}

</style>

</head>

<body>

<h1>Detailed XML Content Mistake Report</h1>

<div class="description">

<p>
This report shows the exact detected mistake,
the exact tag containing the mistake, and the
meaningful surrounding context.
</p>

<p>
Parent and sibling tags are not shown unless they
directly contain the detected content.
</p>

</div>

{''.join(cards)}

</body>

</html>

"""

    DETAIL_REPORT.write_text(
        html_content,
        encoding="utf-8"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("XML / HTML CONTENT COMPARISON TOOL")
    print("=" * 70)

    print("\nReading source...")
    source_records = parse_raw_file(
        SOURCE_FILE
    )

    print(
        f"Source text records: "
        f"{len(source_records)}"
    )

    print("\nReading converted XML...")
    converted_records = parse_raw_file(
        CONVERTED_FILE
    )

    print(
        f"Converted text records: "
        f"{len(converted_records)}"
    )

    # --------------------------------------------------------
    # Build tokens
    # --------------------------------------------------------

    source_tokens = build_tokens(
        source_records
    )

    converted_tokens = build_tokens(
        converted_records
    )

    print(
        f"\nSource tokens: "
        f"{len(source_tokens)}"
    )

    print(
        f"Converted tokens: "
        f"{len(converted_tokens)}"
    )

    # --------------------------------------------------------
    # Generate cleaned files
    # --------------------------------------------------------

    print("\nGenerating cleaned files...")

    generate_cleaned_file(
        SOURCE_FILE,
        SOURCE_CLEANED
    )

    generate_cleaned_file(
        CONVERTED_FILE,
        CONVERTED_CLEANED
    )

    print(
        f"Created: {SOURCE_CLEANED.name}"
    )

    print(
        f"Created: {CONVERTED_CLEANED.name}"
    )

    # --------------------------------------------------------
    # Compare
    # --------------------------------------------------------

    print("\nComparing content...")

    changes = compare_tokens(
        source_tokens,
        converted_tokens
    )

    print(
        f"Detected differences: "
        f"{len(changes)}"
    )

    # --------------------------------------------------------
    # Reports
    # --------------------------------------------------------

    print("\nGenerating main report...")

    generate_main_report(
        changes,
        source_tokens,
        converted_tokens
    )

    print(
        f"Created: {MAIN_REPORT.name}"
    )

    print("\nGenerating detailed mistake report...")

    generate_detail_report(
        changes,
        source_tokens,
        converted_tokens
    )

    print(
        f"Created: {DETAIL_REPORT.name}"
    )

    # --------------------------------------------------------
    # Finish
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("COMPLETED")
    print("=" * 70)

    print("\nOutput files:")

    print(f"1. {SOURCE_CLEANED}")
    print(f"2. {CONVERTED_CLEANED}")
    print(f"3. {MAIN_REPORT}")
    print(f"4. {DETAIL_REPORT}")


if __name__ == "__main__":
    main()