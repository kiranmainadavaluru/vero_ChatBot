"""
Document loader dispatcher.

Picks the correct loader for a file based on its extension and
returns pages in the same (page_number, text) shape regardless of
source format, so chunking and everything downstream never needs to
know or care what kind of file it came from.
"""
import os

import pdf_loader
import docx_loader
import excel_loader
import csv_loader
import txt_loader
import pptx_loader
import html_loader
import json_loader
import xml_loader

_LOADERS = {
    ".pdf": pdf_loader.load_pdf,
    ".docx": docx_loader.load_docx,
    ".xlsx": excel_loader.load_excel,
    ".xls": excel_loader.load_excel,
    ".csv": csv_loader.load_csv,
    ".txt": txt_loader.load_txt,
    ".md": txt_loader.load_txt,
    ".pptx": pptx_loader.load_pptx,
    ".html": html_loader.load_html,
    ".htm": html_loader.load_html,
    ".json": json_loader.load_json,
    ".xml": xml_loader.load_xml,
}


def load_document(file_path):
    """
    Load any supported document and return (page_number, text) tuples.

    Raises ValueError for unsupported extensions, including .doc
    (legacy binary Word), which needs to be converted to .docx first.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".doc":
        raise ValueError(
            "Legacy .doc files aren't supported. Please convert to "
            ".docx (e.g. via Word or LibreOffice) and re-upload."
        )

    loader = _LOADERS.get(ext)
    if loader is None:
        raise ValueError(f"Unsupported file type: {ext}")

    return loader(file_path)