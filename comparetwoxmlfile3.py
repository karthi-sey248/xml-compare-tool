from pathlib import Path
from difflib import SequenceMatcher
import re
import html


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SOURCE_FILE = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi1\Plain_Html.html"
CONVERTED_FILE = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi1\tex-pre-xml.xml"

SOURCE_CLEANED_FILE = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi1\source_cleaned.html"
CONVERTED_CLEANED_FILE = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi1\converted_cleaned.html"

REPORT_FILE = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi1\content_comparison_report1.html"


# ============================================================
# TOKEN PATTERN
# ============================================================

TOKEN_PATTERN = re.compile(
    r"</?b>|</?i>|[\w]+(?:[-'][\w]+)*|[^\w\s]",
    re.UNICODE
)


# ============================================================
# TOKEN OBJECT
# ============================================================

class Token:

    def __init__(self, text, line):
        self.text = text
        self.line = line

    def __repr__(self):
        return f"Token({self.text!r}, line={self.line})"


# ============================================================
# READ FILE
# ============================================================

def read_file(path):

    return path.read_text(
        encoding="utf-8",
        errors="ignore"
    )


# ============================================================
# CLEAN ONE LINE
#
# Remove all tags except <b> and <i>.
# Keep the original line number.
# ============================================================

def clean_line(line):

    # Keep <b>, </b>, <i>, </i>
    placeholders = {
        "<b>": "___KEEP_B_OPEN___",
        "</b>": "___KEEP_B_CLOSE___",
        "<i>": "___KEEP_I_OPEN___",
        "</i>": "___KEEP_I_CLOSE___",
    }

    temp = line

    for tag, placeholder in placeholders.items():
        temp = temp.replace(tag, placeholder)

    # Remove all remaining tags
    temp = re.sub(
        r"<[^>]*>",
        "",
        temp
    )

    # Restore b/i tags
    for tag, placeholder in placeholders.items():
        temp = temp.replace(
            placeholder,
            tag
        )

    # Decode HTML entities
    temp = html.unescape(temp)

    # Normalize spaces inside the line
    temp = re.sub(
        r"[ \t]+",
        " ",
        temp
    )

    # Remove spaces before punctuation
    temp = re.sub(
        r"\s+([,.;:!?])",
        r"\1",
        temp
    )

    # Add space after punctuation where appropriate
    temp = re.sub(
        r"([,.;:!?])(?=[A-Za-z])",
        r"\1 ",
        temp
    )

    return temp.strip()


# ============================================================
# CLEAN FILE + CREATE LINE-AWARE TOKENS
# ============================================================

def clean_file_with_lines(content):

    lines = content.splitlines()

    cleaned_lines = []
    tokens = []

    for line_number, original_line in enumerate(
        lines,
        start=1
    ):

        cleaned = clean_line(original_line)

        # ----------------------------------------------------
        # IMPORTANT:
        # Always preserve one entry for every original line.
        # ----------------------------------------------------

        cleaned_lines.append(cleaned)

        # Empty line என்றால் token இல்லை
        if not cleaned:
            continue

        # ----------------------------------------------------
        # Tokenize current line
        # ----------------------------------------------------

        line_tokens = TOKEN_PATTERN.findall(
            cleaned
        )

        for token in line_tokens:

            tokens.append(
                Token(
                    token,
                    line_number
                )
            )

    # IMPORTANT:
    # Do NOT use " ".join()
    # Use "\n".join() to preserve line breaks.
    cleaned_text = "\n".join(
        cleaned_lines
    )

    return cleaned_text, tokens

# ============================================================
# TOKEN COMPARISON VALUE
# ============================================================

def comparison_value(token):

    return token.text


# ============================================================
# GET CONTEXT RANGE
# ============================================================

def get_context_range(
    tokens,
    start,
    end,
    context_size=12
):

    context_start = max(
        0,
        start - context_size
    )

    context_end = min(
        len(tokens),
        end + context_size
    )

    return context_start, context_end


# ============================================================
# BUILD CONTEXT HTML
#
# Highlight happens INSIDE Source Context /
# Converted Context.
# ============================================================

def build_context_html(
    tokens,
    context_start,
    context_end,
    highlight_start,
    highlight_end,
    highlight_class
):
    """
    Build context while preserving the ORIGINAL
    source/converted line breaks.
    """

    result = []

    previous_line = None

    for index in range(
        context_start,
        context_end
    ):

        token_obj = tokens[index]

        token = token_obj.text
        current_line = token_obj.line

        # ----------------------------------------------------
        # Preserve original line breaks
        # ----------------------------------------------------

        if previous_line is not None:

            if current_line > previous_line:

                for _ in range(
                    current_line - previous_line
                ):
                    result.append("<br>")

        previous_line = current_line

        # ----------------------------------------------------
        # b / i tags
        # ----------------------------------------------------

        if token in (
            "<b>",
            "</b>",
            "<i>",
            "</i>"
        ):

            result.append(token)

            continue

        escaped = html.escape(token)

        # ----------------------------------------------------
        # Highlight
        # ----------------------------------------------------

        if (
            highlight_start <= index < highlight_end
        ):

            result.append(
                f'<span class="{highlight_class}">'
                f'{escaped}'
                f'</span>'
            )

        else:

            result.append(escaped)

        # ----------------------------------------------------
        # Normal spacing
        # ----------------------------------------------------

        if index < context_end - 1:

            next_token = tokens[index + 1].text

            # Don't add space before punctuation
            if next_token not in (
                ",",
                ".",
                ";",
                ":",
                "!",
                "?",
                ")",
                "]",
                "}"
            ):

                # Don't add space after opening punctuation
                if token not in (
                    "(",
                    "[",
                    "{"
                ):

                    result.append(" ")

    return "".join(result)

# ============================================================
# COMPARE
# ============================================================

def compare_content(
    source_tokens,
    converted_tokens
):

    source_values = [
        comparison_value(token)
        for token in source_tokens
    ]

    converted_values = [
        comparison_value(token)
        for token in converted_tokens
    ]

    matcher = SequenceMatcher(
        None,
        source_values,
        converted_values,
        autojunk=False
    )

    differences = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag == "equal":
            continue

        # ----------------------------------------------------
        # SOURCE CONTEXT
        # ----------------------------------------------------

        source_context_start, source_context_end = (
            get_context_range(
                source_tokens,
                i1,
                i2
            )
        )

        # ----------------------------------------------------
        # CONVERTED CONTEXT
        # ----------------------------------------------------

        converted_context_start, converted_context_end = (
            get_context_range(
                converted_tokens,
                j1,
                j2
            )
        )

        # ----------------------------------------------------
        # ADDED
        # ----------------------------------------------------

        if tag == "insert":

            source_context = build_context_html(
                source_tokens,
                source_context_start,
                source_context_end,
                -1,
                -1,
                "removed-highlight"
            )

            converted_context = build_context_html(
                converted_tokens,
                converted_context_start,
                converted_context_end,
                j1,
                j2,
                "added-highlight"
            )

            change_type = "Added"

            source_line = "-"

            if j1 < len(converted_tokens):
                converted_line = (
                    converted_tokens[j1].line
                )
            else:
                converted_line = "-"

        # ----------------------------------------------------
        # REMOVED
        # ----------------------------------------------------

        elif tag == "delete":

            source_context = build_context_html(
                source_tokens,
                source_context_start,
                source_context_end,
                i1,
                i2,
                "removed-highlight"
            )

            converted_context = build_context_html(
                converted_tokens,
                converted_context_start,
                converted_context_end,
                -1,
                -1,
                "added-highlight"
            )

            change_type = "Removed"

            if i1 < len(source_tokens):
                source_line = source_tokens[i1].line
            else:
                source_line = "-"

            converted_line = "-"

        # ----------------------------------------------------
        # CHANGED
        # ----------------------------------------------------

        else:

            source_context = build_context_html(
                source_tokens,
                source_context_start,
                source_context_end,
                i1,
                i2,
                "removed-highlight"
            )

            converted_context = build_context_html(
                converted_tokens,
                converted_context_start,
                converted_context_end,
                j1,
                j2,
                "added-highlight"
            )

            change_type = "Changed"

            if i1 < len(source_tokens):
                source_line = source_tokens[i1].line
            else:
                source_line = "-"

            if j1 < len(converted_tokens):
                converted_line = converted_tokens[j1].line
            else:
                converted_line = "-"

        differences.append({
            "type": change_type,
            "source_line": source_line,
            "converted_line": converted_line,
            "source_context": source_context,
            "converted_context": converted_context
        })

    return differences


# ============================================================
# GENERATE HTML REPORT
# ============================================================

def generate_report(differences):

    added_count = sum(
        1
        for x in differences
        if x["type"] == "Added"
    )

    removed_count = sum(
        1
        for x in differences
        if x["type"] == "Removed"
    )

    changed_count = sum(
        1
        for x in differences
        if x["type"] == "Changed"
    )

    rows = []

    for index, diff in enumerate(
        differences,
        start=1
    ):

        rows.append(
            f"""
            <tr>

                <td class="number">
                    {index}
                </td>

                <td>
                    <span class="change-type {diff["type"].lower()}">
                        {diff["type"]}
                    </span>
                </td>

                <td class="line-number">
                    {diff["source_line"]}
                </td>

                <td class="line-number">
                    {diff["converted_line"]}
                </td>

                <td class="context source-context">
                    {diff["source_context"]}
                </td>

                <td class="context converted-context">
                    {diff["converted_context"]}
                </td>

            </tr>
            """
        )

    report = f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<title>XML Content Comparison Report</title>

<style>

body {{
    font-family: Arial, Helvetica, sans-serif;
    margin: 0;
    padding: 25px;
    background: #f4f6f8;
    color: #222;
}}

h1 {{
    margin-bottom: 8px;
}}

.description {{
    color: #666;
    margin-bottom: 25px;
}}

.summary {{
    display: flex;
    gap: 15px;
    margin-bottom: 25px;
}}

.card {{
    background: white;
    padding: 15px 25px;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    min-width: 120px;
}}

.card-title {{
    font-size: 13px;
    color: #666;
}}

.card-value {{
    font-size: 25px;
    font-weight: bold;
    margin-top: 5px;
}}

.toolbar {{
    background: white;
    padding: 15px;
    margin-bottom: 15px;
    border-radius: 8px;
}}

input {{
    width: 350px;
    padding: 10px;
    border: 1px solid #ccc;
    border-radius: 5px;
}}

select {{
    padding: 10px;
    margin-left: 10px;
    border: 1px solid #ccc;
    border-radius: 5px;
}}

.table-container {{
    background: white;
    border-radius: 8px;
    overflow: auto;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}}

table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}}

thead {{
    position: sticky;
    top: 0;
    z-index: 10;
}}

th {{
    background: #263238;
    color: white;
    padding: 13px;
    text-align: left;
}}

td {{
    padding: 12px;
    border-bottom: 1px solid #e5e5e5;
    vertical-align: top;
}}

tr:hover {{
    background: #fafafa;
}}

.number {{
    width: 45px;
    text-align: center;
}}

.line-number {{
    width: 75px;
    text-align: center;
    font-family: Consolas, monospace;
    font-weight: bold;
}}

.context {{
    font-family: Consolas, "Courier New", monospace;
    font-size: 14px;
    line-height: 1.8;
    word-break: break-word;
}}

.source-context {{
    width: 30%;
}}

.converted-context {{
    width: 30%;
}}

.removed-highlight {{
    background: #ffb3b3;
    color: #9b0000;
    font-weight: bold;
    padding: 2px 4px;
    border-radius: 3px;
    text-decoration: line-through;
}}

.added-highlight {{
    background: #b9f6c3;
    color: #087f23;
    font-weight: bold;
    padding: 2px 4px;
    border-radius: 3px;
}}

.change-type {{
    padding: 5px 9px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: bold;
}}

.change-type.added {{
    background: #d8f8df;
    color: #087f23;
}}

.change-type.removed {{
    background: #ffdada;
    color: #b00020;
}}

.change-type.changed {{
    background: #fff0c2;
    color: #8a5a00;
}}

.legend {{
    margin-top: 15px;
    background: white;
    padding: 15px;
    border-radius: 8px;
}}

.legend span {{
    display: inline-block;
    padding: 5px 9px;
    margin-right: 15px;
    border-radius: 3px;
    font-weight: bold;
}}

.legend-removed {{
    background: #ffb3b3;
    color: #9b0000;
}}

.legend-added {{
    background: #b9f6c3;
    color: #087f23;
}}

</style>

</head>

<body>

<h1>XML Content Comparison Report</h1>

<div class="description">

Source:
<strong>{SOURCE_FILE.name}</strong>

&nbsp;&nbsp;→&nbsp;&nbsp;

Converted:
<strong>{CONVERTED_FILE.name}</strong>

</div>


<div class="summary">

<div class="card">
    <div class="card-title">Total Changes</div>
    <div class="card-value">
        {len(differences)}
    </div>
</div>

<div class="card">
    <div class="card-title">Added</div>
    <div class="card-value">
        {added_count}
    </div>
</div>

<div class="card">
    <div class="card-title">Removed</div>
    <div class="card-value">
        {removed_count}
    </div>
</div>

<div class="card">
    <div class="card-title">Changed</div>
    <div class="card-value">
        {changed_count}
    </div>
</div>

</div>


<div class="toolbar">

<input
    type="text"
    id="searchBox"
    placeholder="Search changes..."
    onkeyup="filterTable()"
/>

<select
    id="changeFilter"
    onchange="filterTable()"
>

<option value="All">All Changes</option>
<option value="Added">Added</option>
<option value="Removed">Removed</option>
<option value="Changed">Changed</option>

</select>

</div>


<div class="table-container">

<table id="comparisonTable">

<thead>

<tr>

<th style="width:45px;">
    #
</th>

<th style="width:90px;">
    Change Type
</th>

<th style="width:85px;">
    Source Line
</th>

<th style="width:100px;">
    Converted Line
</th>

<th>
    Source Context
</th>

<th>
    Converted Context
</th>

</tr>

</thead>

<tbody>

{''.join(rows)}

</tbody>

</table>

</div>


<div class="legend">

<strong>Highlight:</strong>

<span class="legend-removed">
Removed / Changed in Source
</span>

<span class="legend-added">
Added / Changed in Converted
</span>

</div>


<script>

function filterTable() {{

    const search =
        document
        .getElementById("searchBox")
        .value
        .toLowerCase();

    const filter =
        document
        .getElementById("changeFilter")
        .value;

    const rows =
        document.querySelectorAll(
            "#comparisonTable tbody tr"
        );


    rows.forEach(row => {{

        const text =
            row.innerText.toLowerCase();

        const type =
            row.querySelector(
                ".change-type"
            )?.innerText || "";

        const searchMatch =
            text.includes(search);

        const typeMatch =
            filter === "All" ||
            type === filter;

        row.style.display =
            searchMatch && typeMatch
            ? ""
            : "none";

    }});

}}

</script>

</body>

</html>
"""

    REPORT_FILE.write_text(
        report,
        encoding="utf-8"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("XML / HTML CONTENT COMPARISON")
    print("=" * 70)

    # --------------------------------------------------------
    # Read
    # --------------------------------------------------------

    print("\nReading source...")
    source_original = read_file(
        SOURCE_FILE
    )

    print("Reading converted...")
    converted_original = read_file(
        CONVERTED_FILE
    )


    # --------------------------------------------------------
    # Clean + line mapping
    # --------------------------------------------------------

    print("\nCleaning source...")
    source_cleaned, source_tokens = (
        clean_file_with_lines(
            source_original
        )
    )

    print("Cleaning converted...")
    converted_cleaned, converted_tokens = (
        clean_file_with_lines(
            converted_original
        )
    )


    # --------------------------------------------------------
    # Save cleaned files
    # --------------------------------------------------------

    SOURCE_CLEANED_FILE.write_text(
        source_cleaned,
        encoding="utf-8"
    )

    CONVERTED_CLEANED_FILE.write_text(
        converted_cleaned,
        encoding="utf-8"
    )


    # --------------------------------------------------------
    # Compare
    # --------------------------------------------------------

    print("\nComparing content...")

    differences = compare_content(
        source_tokens,
        converted_tokens
    )


    # --------------------------------------------------------
    # Generate report
    # --------------------------------------------------------

    print("\nGenerating HTML report...")

    generate_report(
        differences
    )


    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    added = sum(
        1
        for x in differences
        if x["type"] == "Added"
    )

    removed = sum(
        1
        for x in differences
        if x["type"] == "Removed"
    )

    changed = sum(
        1
        for x in differences
        if x["type"] == "Changed"
    )

    print("\n" + "=" * 70)

    print(
        f"Total changes : {len(differences)}"
    )

    print(
        f"Added         : {added}"
    )

    print(
        f"Removed       : {removed}"
    )

    print(
        f"Changed       : {changed}"
    )

    print("\nGenerated:")

    print(
        f"Source cleaned    : {SOURCE_CLEANED_FILE}"
    )

    print(
        f"Converted cleaned : {CONVERTED_CLEANED_FILE}"
    )

    print(
        f"Comparison report : {REPORT_FILE}"
    )

    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()