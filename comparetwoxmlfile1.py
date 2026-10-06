from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag, Comment
import re


# ============================================================
# FILE PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SOURCE_FILE = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi\Plain_Html.html"
CONVERTED_FILE = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi\tex-pre-xml - Copy.xml"

SOURCE_OUTPUT = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi\source_cleaned_1.html"
CONVERTED_OUTPUT = BASE_DIR / r"D:\karthikeyan\Testing\21-09-2026\toKarthi\converted_cleaned_1.xml"


# Only these tags should remain
ALLOWED_TAGS = {"b", "i"}


# ============================================================
# REMOVE ALL TAGS EXCEPT <b> AND <i>
# ============================================================

def extract_clean_content(file_path):
    """
    Remove all tags except <b> and <i>.
    Preserve text content and add spacing where
    removed tags join separate text portions.
    """

    content = file_path.read_text(encoding="utf-8-sig")

    if file_path.suffix.lower() == ".xml":
        soup = BeautifulSoup(content, "xml")
    else:
        soup = BeautifulSoup(content, "html.parser")

    def process_node(node):

        if isinstance(node, Comment):
            return ""

        if isinstance(node, NavigableString):
            return str(node)

        if isinstance(node, Tag):

            inner_content = "".join(
                process_node(child)
                for child in node.children
            )

            # Keep <b> and <i>
            if node.name.lower() in ALLOWED_TAGS:
                return f"<{node.name.lower()}>{inner_content}</{node.name.lower()}>"

            # Remove tag but preserve its content
            return f" {inner_content} "

        return ""

    cleaned_content = process_node(soup)

    # --------------------------------------------------------
    # Add missing spaces between joined text
    # --------------------------------------------------------

    # Example:
    # "2.Literature" -> "2. Literature"
    cleaned_content = re.sub(
        r'(\d+\.)([A-Za-z])',
        r'\1 \2',
        cleaned_content
    )

    # Example:
    # "review2.1Net" -> "review 2.1 Net"
    cleaned_content = re.sub(
        r'([a-zA-Z])(\d+\.)',
        r'\1 \2',
        cleaned_content
    )

    cleaned_content = re.sub(
        r'(\d+\.\d+)([A-Za-z])',
        r'\1 \2',
        cleaned_content
    )

    # Multiple spaces -> single space
    cleaned_content = re.sub(
        r'[ \t]+',
        ' ',
        cleaned_content
    )

    # Clean spaces around line breaks
    cleaned_content = re.sub(
        r'[ \t]*\n[ \t]*',
        '\n',
        cleaned_content
    )

    # Multiple blank lines -> one
    cleaned_content = re.sub(
        r'\n{3,}',
        '\n\n',
        cleaned_content
    )

    return cleaned_content.strip()



# ============================================================
# NORMALIZE WHITESPACE
# ============================================================

def normalize_content(content):
    content = content.replace("\r\n", "\n")
    content = content.replace("\r", "\n")

    # Multiple spaces -> single space
    content = re.sub(r'[ \t]+', ' ', content)

    # Remove space before punctuation
    content = re.sub(r'\s+([,.;:!?])', r'\1', content)

    # Remove space before closing brackets
    content = re.sub(r'\s+([)\]])', r'\1', content)

    # Remove space after opening brackets
    content = re.sub(r'([(\[])\s+', r'\1', content)

    # Clean line breaks
    content = re.sub(r' *\n *', '\n', content)

    # Multiple blank lines -> one
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content.strip()

# ============================================================
# MAIN
# ============================================================

def main():

    print("Reading source file...")
    source_content = extract_clean_content(SOURCE_FILE)

    print("Reading converted file...")
    converted_content = extract_clean_content(CONVERTED_FILE)

    print("Cleaning source content...")
    source_content = normalize_content(source_content)

    print("Cleaning converted content...")
    converted_content = normalize_content(converted_content)

    # --------------------------------------------------------
    # Save source separately
    # --------------------------------------------------------

    SOURCE_OUTPUT.write_text(
        source_content,
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Save converted separately
    # --------------------------------------------------------

    CONVERTED_OUTPUT.write_text(
        converted_content,
        encoding="utf-8"
    )

    print()
    print("========================================")
    print("Files generated successfully")
    print("========================================")
    print()
    print(f"Source cleaned file    : {SOURCE_OUTPUT}")
    print(f"Converted cleaned file : {CONVERTED_OUTPUT}")
    print()


if __name__ == "__main__":
    main()