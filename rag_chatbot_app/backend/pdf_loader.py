"""
PDF document loader.

Extracts text page-by-page instead of flattening the whole document
into one string, so downstream chunking can tag each chunk with the
exact page it came from.
"""
from PyPDF2 import PdfReader


def load_pdf(file_path):
    """
    Extract text from a PDF, one page at a time.

    Returns a list of (page_number, text) tuples. page_number is
    1-based, matching what a human would see in a PDF viewer.
    """
    reader = PdfReader(file_path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append((i, text))

    total_chars = sum(len(text) for _, text in pages)
    print(f"✅ Extracted {total_chars} characters from {len(pages)} PDF pages")
    return pages