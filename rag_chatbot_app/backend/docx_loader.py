"""
Word (.docx) loader.

.docx has no reliable concept of "pages" outside of a rendering
engine (pagination depends on fonts, margins, screen size at render
time) so the whole document is returned as a single unit
(page_number=-1). Paragraph breaks are preserved so the text splitter
still has natural boundaries to chunk on.
"""
import docx


def load_docx(file_path):
    document = docx.Document(file_path)
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    text = "\n\n".join(paragraphs)

    print(f"✅ Extracted {len(text)} characters from DOCX")
    return [(-1, text)]