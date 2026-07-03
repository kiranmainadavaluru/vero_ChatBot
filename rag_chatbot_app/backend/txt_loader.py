"""
Plain text loader — also used for Markdown (.md).

Markdown source is already readable as-is (headings, lists, etc. are
plain characters), so no special parsing is applied; the raw text is
passed straight through to chunking.
"""


def load_txt(file_path):
    with open(file_path, encoding="utf-8", errors="ignore") as f:
        text = f.read()

    print(f"✅ Extracted {len(text)} characters from text file")
    return [(-1, text)]