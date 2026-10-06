from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag
import re
import difflib


# ============================================================
# FILE PATHS
# ============================================================

SOURCE_HTML = r"D:\karthikeyan\Testing\21-09-2026\Process\Plain_Html.html"
CONVERTED_XML = r"D:\karthikeyan\Testing\21-09-2026\Process\tex-pre-xml.xml"

REPORT_FILE = r"D:\karthikeyan\Testing\21-09-2026\Process\xml_content_comparison_report.txt"


# ============================================================
# TAGS THAT MUST BE PRESERVED
# ============================================================

ALLOWED_TAGS = {"b", "i"}


# ============================================================
# EXTRACT CONTENT
# ============================================================

def extract_content(file_path):
    """
    Remove all tags except <b> and <i>.
    Keep the text content of all other tags.
    """

    path = Path(file_path)

    content = path.read_text(
        encoding="utf-8-sig",
        errors="replace"
    )

    # Use HTML parser for HTML
    # Use XML parser for XML
    if path.suffix.lower() == ".xml":
        soup = BeautifulSoup(content, "xml")
    else:
        soup = BeautifulSoup(content, "html.parser")

    def process_node(node):

        # Plain text
        if isinstance(node, NavigableString):
            return str(node)

        # XML/HTML tag
        if isinstance(node, Tag):

            inner_content = "".join(
                process_node(child)
                for child in node.children
            )

            # Keep only <b> and <i>
            if node.name.lower() in ALLOWED_TAGS:
                return f"<{node.name.lower()}>{inner_content}</{node.name.lower()}>"

            # Ignore the tag itself,
            # but keep its content
            return inner_content

        return ""

    result = process_node(soup)

    return normalize_whitespace(result)


# ============================================================
# NORMALIZE WHITESPACE
# ============================================================

def normalize_whitespace(text):
    """
    Normalize spaces, tabs and line breaks.
    """

    # Convert multiple whitespace characters to one space
    text = re.sub(r"\s+", " ", text)

    # Remove space immediately inside b/i tags
    text = re.sub(r"<(b|i)>\s+", r"<\1>", text)
    text = re.sub(r"\s+</(b|i)>", r"</\1>", text)

    return text.strip()


# ============================================================
# COMPARE
# ============================================================

def compare_content(source, converted):

    if source == converted:
        return True, []

    matcher = difflib.SequenceMatcher(
        None,
        source,
        converted
    )

    differences = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag == "equal":
            continue

        source_text = source[i1:i2]
        converted_text = converted[j1:j2]

        differences.append({
            "type": tag,
            "source": source_text,
            "converted": converted_text
        })

    return False, differences


# ============================================================
# GENERATE REPORT
# ============================================================

def generate_report(source, converted, differences):

    lines = []

    lines.append("=" * 80)
    lines.append("HTML vs XML CONTENT COMPARISON REPORT")
    lines.append("=" * 80)

    lines.append("")
    lines.append("Source File   : Plain_Html.html")
    lines.append("Converted File: tex-pre-xml.xml")

    lines.append("")
    lines.append("-" * 80)

    if not differences:
        lines.append("RESULT: MATCH")
        lines.append("")
        lines.append(
            "After removing all tags except <b> and <i>, "
            "the content is identical."
        )

    else:
        lines.append("RESULT: DIFFERENT")
        lines.append("")
        lines.append(
            f"Number of differences: {len(differences)}"
        )

        lines.append("")
        lines.append("-" * 80)

        for index, diff in enumerate(differences, start=1):

            lines.append(f"Difference #{index}")
            lines.append(f"Type: {diff['type']}")

            lines.append("")
            lines.append("SOURCE:")
            lines.append(diff["source"])

            lines.append("")
            lines.append("CONVERTED XML:")
            lines.append(diff["converted"])

            lines.append("")
            lines.append("-" * 80)

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    print("Reading source HTML...")
    source_content = extract_content(SOURCE_HTML)

    print("Reading converted XML...")
    converted_content = extract_content(CONVERTED_XML)

    print("Comparing content...")

    is_match, differences = compare_content(
        source_content,
        converted_content
    )

    report = generate_report(
        source_content,
        converted_content,
        differences
    )

    # Save report
    Path(REPORT_FILE).write_text(
        report,
        encoding="utf-8"
    )

    print()
    print("=" * 60)

    if is_match:
        print("RESULT: MATCH")
        print("Content is identical.")
    else:
        print("RESULT: DIFFERENT")
        print(f"Differences found: {len(differences)}")

    print("=" * 60)

    print()
    print(f"Report generated:")
    print(REPORT_FILE)


if __name__ == "__main__":
    main()