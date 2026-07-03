"""
HTML loader.

Strips tags, scripts, and styles down to visible text using
BeautifulSoup. No page concept, so returned as a single unit
(page_number=-1).
"""
from bs4 import BeautifulSoup


def load_html(file_path):
    with open(file_path, encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())

    print(f"✅ Extracted {len(text)} characters from HTML")
    return [(-1, text)]