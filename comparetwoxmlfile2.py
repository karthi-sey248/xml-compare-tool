from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag, Comment
import difflib
import html
import re
import unicodedata


# ============================================================
# FILE PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SOURCE_FILE = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi1\Plain_Html.html"
CONVERTED_FILE = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi1\tex-pre-xml.xml"

SOURCE_CLEANED_FILE = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi1\source_cleaned_1.html"
CONVERTED_CLEANED_FILE = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi1\converted_cleaned_1.xml"

REPORT_FILE = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi1\content_comparison_report.html"


# Only these tags are allowed to remain
ALLOWED_TAGS = {"b", "i"}

# Number of words shown before/after each difference
CONTEXT_SIZE = 12


# ============================================================
# READ FILE
# ============================================================

def read_file(file_path):

    content = file_path.read_text(
        encoding="utf-8-sig"
    )

    if file_path.suffix.lower() == ".xml":
        soup = BeautifulSoup(content, "xml")
    else:
        soup = BeautifulSoup(content, "html.parser")

    return soup


# ============================================================
# REMOVE TAGS EXCEPT B AND I
# ============================================================

def clean_file(file_path):

    soup = read_file(file_path)

    def process_node(node):

        # Ignore comments
        if isinstance(node, Comment):
            return ""

        # Text
        if isinstance(node, NavigableString):
            return str(node)

        # Tag
        if isinstance(node, Tag):

            inner_content = "".join(
                process_node(child)
                for child in node.children
            )

            tag_name = node.name.lower()

            # Keep only <b> and <i>
            if tag_name in ALLOWED_TAGS:

                return (
                    f"<{tag_name}>"
                    f"{inner_content}"
                    f"</{tag_name}>"
                )

            # Remove tag but keep content
            # Space is added to avoid words joining together.
            return f" {inner_content} "

        return ""

    cleaned = process_node(soup)

    # Unicode normalization
    cleaned = unicodedata.normalize(
        "NFC",
        cleaned
    )

    # Normalize line endings
    cleaned = cleaned.replace("\r\n", "\n")
    cleaned = cleaned.replace("\r", "\n")

    # Multiple spaces -> single space
    cleaned = re.sub(
        r"[ \t]+",
        " ",
        cleaned
    )

    # Remove space before punctuation
    cleaned = re.sub(
        r"\s+([,.;:!?])",
        r"\1",
        cleaned
    )

    # Remove space after opening brackets
    cleaned = re.sub(
        r"([(\[])\s+",
        r"\1",
        cleaned
    )

    # Remove space before closing brackets
    cleaned = re.sub(
        r"\s+([)\]])",
        r"\1",
        cleaned
    )

    # Clean line spacing
    cleaned = re.sub(
        r"[ \t]*\n[ \t]*",
        "\n",
        cleaned
    )

    # Multiple blank lines -> one
    cleaned = re.sub(
        r"\n{3,}",
        "\n\n",
        cleaned
    )

    return cleaned.strip()


# ============================================================
# TOKENIZE CONTENT
# ============================================================

def tokenize(content):

    """
    Split content into words, punctuation and
    <b>/<i> markers.

    Example:

    Hello <b>world</b>.

    becomes:

    Hello
    <b>
    world
    </b>
    .
    """

    return re.findall(
        r"</?[bi]>|[\w]+(?:[-'’][\w]+)*|[^\w\s]",
        content,
        flags=re.UNICODE
    )


# ============================================================
# DISPLAY TOKEN
# ============================================================

def make_display_text(tokens):

    result = []

    for token in tokens:

        result.append(token)

    text = " ".join(result)

    # Fix punctuation spacing
    text = re.sub(
        r"\s+([,.;:!?])",
        r"\1",
        text
    )

    text = re.sub(
        r"([(\[])\s+",
        r"\1",
        text
    )

    text = re.sub(
        r"\s+([)\]])",
        r"\1",
        text
    )

    return text.strip()


# ============================================================
# HTML CONTENT DISPLAY
# ============================================================

def make_html_content(tokens):

    result = []

    for token in tokens:

        if token == "<b>":
            result.append("<b>")

        elif token == "</b>":
            result.append("</b>")

        elif token == "<i>":
            result.append("<i>")

        elif token == "</i>":
            result.append("</i>")

        else:
            result.append(
                html.escape(token)
            )
            result.append(" ")

    result = "".join(result)

    # Fix punctuation spacing
    result = re.sub(
        r"\s+([,.;:!?])",
        r"\1",
        result
    )

    result = re.sub(
        r"([(\[])\s+",
        r"\1",
        result
    )

    result = re.sub(
        r"\s+([)\]])",
        r"\1",
        result
    )

    return result.strip()


# ============================================================
# CONTEXT
# ============================================================

def get_context(
    tokens,
    start,
    end,
    context_size=CONTEXT_SIZE
):

    left = max(
        0,
        start - context_size
    )

    right = min(
        len(tokens),
        end + context_size
    )

    context_tokens = tokens[left:right]

    context = make_display_text(
        context_tokens
    )

    if left > 0:
        context = "... " + context

    if right < len(tokens):
        context = context + " ..."

    return context


# ============================================================
# CHANGE TYPE
# ============================================================

def determine_change_type(
    source_tokens,
    converted_tokens
):

    if source_tokens and not converted_tokens:
        return "Removed"

    if converted_tokens and not source_tokens:
        return "Added"

    return "Changed"


# ============================================================
# COMPARE
# ============================================================

def compare_content(
    source_content,
    converted_content
):

    source_tokens = tokenize(
        source_content
    )

    converted_tokens = tokenize(
        converted_content
    )

    # Case-sensitive comparison
    matcher = difflib.SequenceMatcher(
        None,
        source_tokens,
        converted_tokens,
        autojunk=False
    )

    differences = []

    for tag, s1, s2, c1, c2 in matcher.get_opcodes():

        # Same content
        if tag == "equal":
            continue

        source_part = source_tokens[s1:s2]
        converted_part = converted_tokens[c1:c2]

        change_type = determine_change_type(
            source_part,
            converted_part
        )

        source_context = get_context(
            source_tokens,
            s1,
            s2
        )

        converted_context = get_context(
            converted_tokens,
            c1,
            c2
        )

        differences.append({

            "number": len(differences) + 1,

            "type": change_type,

            "source_context":
                source_context,

            "converted_context":
                converted_context,

            "source_content":
                make_html_content(
                    source_part
                ),

            "converted_content":
                make_html_content(
                    converted_part
                )
        })

    return differences


# ============================================================
# HTML REPORT
# ============================================================

def generate_html_report(
    differences
):

    total = len(differences)

    added = sum(
        1
        for d in differences
        if d["type"] == "Added"
    )

    removed = sum(
        1
        for d in differences
        if d["type"] == "Removed"
    )

    changed = sum(
        1
        for d in differences
        if d["type"] == "Changed"
    )

    if total == 0:
        status = "MATCH"
    else:
        status = "DIFFERENCES FOUND"

    rows = []

    for diff in differences:

        change_type = diff["type"]

        rows.append(
            f"""
            <tr data-type="{change_type.lower()}">

                <td>
                    {diff["number"]}
                </td>

                <td>
                    <span class="badge {change_type.lower()}">
                        {change_type}
                    </span>
                </td>

                <td class="context">
                    {html.escape(
                        diff["source_context"]
                    )}
                </td>

                <td class="context">
                    {html.escape(
                        diff["converted_context"]
                    )}
                </td>

                <td class="source-content">
                    {diff["source_content"] or "—"}
                </td>

                <td class="converted-content">
                    {diff["converted_content"] or "—"}
                </td>

            </tr>
            """
        )

    if not rows:

        rows.append(
            """
            <tr>
                <td colspan="6"
                    class="no-difference">
                    No differences found.
                </td>
            </tr>
            """
        )

    rows_html = "".join(rows)

    report = f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<title>
Source vs Converted Comparison
</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{

    margin: 0;

    padding: 25px;

    font-family:
        Arial,
        Helvetica,
        sans-serif;

    background: #f4f6f8;

    color: #222;
}}

.container {{

    max-width: 1800px;

    margin: auto;
}}

h1 {{

    margin-bottom: 5px;

}}

.subtitle {{

    color: #666;

    margin-bottom: 20px;
}}

.files {{

    background: white;

    padding: 15px;

    border-radius: 8px;

    border: 1px solid #ddd;

    margin-bottom: 15px;

    line-height: 1.8;
}}

.status {{

    font-weight: bold;
}}

.summary {{

    display: grid;

    grid-template-columns:
        repeat(5, 1fr);

    gap: 12px;

    margin-bottom: 15px;
}}

.card {{

    background: white;

    padding: 15px;

    border: 1px solid #ddd;

    border-radius: 8px;
}}

.card-title {{

    font-size: 12px;

    color: #666;

    text-transform: uppercase;
}}

.card-value {{

    font-size: 22px;

    font-weight: bold;

    margin-top: 5px;
}}

.toolbar {{

    background: white;

    padding: 12px;

    border: 1px solid #ddd;

    display: flex;

    gap: 10px;

    border-radius: 8px 8px 0 0;
}}

input,
select {{

    padding: 9px;

    border: 1px solid #bbb;

    border-radius: 5px;

    font-size: 14px;
}}

.table-container {{

    overflow-x: auto;

    background: white;

    border: 1px solid #ddd;

    border-top: none;
}}

table {{

    width: 100%;

    min-width: 1400px;

    border-collapse: collapse;
}}

th {{

    position: sticky;

    top: 0;

    background: #263238;

    color: white;

    padding: 12px;

    text-align: left;
}}

td {{

    border-bottom: 1px solid #ddd;

    padding: 10px;

    vertical-align: top;

    line-height: 1.6;
}}

tr:hover {{

    background: #fafafa;
}}

.context {{

    min-width: 300px;

    color: #555;
}}

.source-content {{

    min-width: 220px;

    background: #fff0f0;
}}

.converted-content {{

    min-width: 220px;

    background: #f0fff2;
}}

.badge {{

    padding: 5px 9px;

    border-radius: 12px;

    font-size: 11px;

    font-weight: bold;
}}

.badge.added {{

    background: #d9f7df;

    color: #176b2c;
}}

.badge.removed {{

    background: #ffe0e0;

    color: #9b2020;
}}

.badge.changed {{

    background: #fff0c7;

    color: #805800;
}}

.no-difference {{

    text-align: center;

    padding: 30px;

    font-weight: bold;
}}

</style>

</head>


<body>

<div class="container">

<h1>
Source vs Converted Content Comparison
</h1>

<div class="subtitle">

Tags are ignored except
<b>&lt;b&gt;</b>
and
<i>&lt;i&gt;</i>.

</div>


<div class="files">

<b>Source:</b>
{html.escape(SOURCE_FILE.name)}

<br>

<b>Converted:</b>
{html.escape(CONVERTED_FILE.name)}

<br>

<b>Status:</b>
<span class="status">
{status}
</span>

</div>


<div class="summary">

<div class="card">

<div class="card-title">
Total Differences
</div>

<div class="card-value">
{total}
</div>

</div>


<div class="card">

<div class="card-title">
Added
</div>

<div class="card-value">
{added}
</div>

</div>


<div class="card">

<div class="card-title">
Removed
</div>

<div class="card-value">
{removed}
</div>

</div>


<div class="card">

<div class="card-title">
Changed
</div>

<div class="card-value">
{changed}
</div>

</div>


<div class="card">

<div class="card-title">
Status
</div>

<div class="card-value">
{status}
</div>

</div>

</div>


<div class="toolbar">

<input
    id="searchBox"
    type="text"
    placeholder="Search content/context..."
    onkeyup="filterTable()"
>


<select
    id="typeFilter"
    onchange="filterTable()"
>

<option value="all">
All Changes
</option>

<option value="added">
Added
</option>

<option value="removed">
Removed
</option>

<option value="changed">
Changed
</option>

</select>

</div>


<div class="table-container">

<table id="comparisonTable">

<thead>

<tr>

<th>#</th>

<th>Change Type</th>

<th>Source Context</th>

<th>Converted Context</th>

<th>Source Content</th>

<th>Converted Content</th>

</tr>

</thead>


<tbody>

{rows_html}

</tbody>

</table>

</div>

</div>


<script>

function filterTable() {{

    const search =
        document
        .getElementById("searchBox")
        .value
        .toLowerCase();

    const type =
        document
        .getElementById("typeFilter")
        .value;

    const rows =
        document.querySelectorAll(
            "#comparisonTable tbody tr"
        );

    rows.forEach(row => {{

        const text =
            row.innerText.toLowerCase();

        const rowType =
            row.dataset.type || "";

        const searchMatch =
            text.includes(search);

        const typeMatch =
            type === "all"
            ||
            rowType === type;

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

    return report


# ============================================================
# MAIN
# ============================================================

def main():

    print("Reading source HTML...")
    source_cleaned = clean_file(
        SOURCE_FILE
    )

    print("Reading converted XML...")
    converted_cleaned = clean_file(
        CONVERTED_FILE
    )


    # Save cleaned source
    SOURCE_CLEANED_FILE.write_text(
        source_cleaned,
        encoding="utf-8"
    )


    # Save cleaned converted
    CONVERTED_CLEANED_FILE.write_text(
        converted_cleaned,
        encoding="utf-8"
    )


    print("Comparing content...")

    differences = compare_content(
        source_cleaned,
        converted_cleaned
    )


    print("Generating HTML report...")

    report = generate_html_report(
        differences
    )


    REPORT_FILE.write_text(
        report,
        encoding="utf-8"
    )


    # Summary
    added = sum(
        1 for d in differences
        if d["type"] == "Added"
    )

    removed = sum(
        1 for d in differences
        if d["type"] == "Removed"
    )

    changed = sum(
        1 for d in differences
        if d["type"] == "Changed"
    )


    print()
    print("=" * 55)
    print("COMPARISON COMPLETED")
    print("=" * 55)

    print(
        f"Source cleaned    : "
        f"{SOURCE_CLEANED_FILE}"
    )

    print(
        f"Converted cleaned : "
        f"{CONVERTED_CLEANED_FILE}"
    )

    print(
        f"HTML report       : "
        f"{REPORT_FILE}"
    )

    print(
        f"Total differences : "
        f"{len(differences)}"
    )

    print(
        f"Added             : "
        f"{added}"
    )

    print(
        f"Removed           : "
        f"{removed}"
    )

    print(
        f"Changed           : "
        f"{changed}"
    )

    print("=" * 55)


if __name__ == "__main__":
    main()