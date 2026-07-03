"""
Text chunking.

Splits (page_number, text) pairs — the common shape every loader in
document_loaders.py returns — into overlapping chunks. Each chunk is
tagged with the page it came from and its position in the document,
so this one function works identically regardless of source format.
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config


def chunk_pages(pages):
    """
    pages: list of (page_number, text) tuples.
    Returns a list of dicts: {content, page_number, chunk_index}.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    chunks = []
    chunk_index = 0
    for page_number, text in pages:
        if not text.strip():
            continue
        for piece in splitter.split_text(text):
            chunks.append({
                "content": piece,
                "page_number": page_number,
                "chunk_index": chunk_index,
            })
            chunk_index += 1

    print(f"✅ Created {len(chunks)} chunks across {len(pages)} page(s)/section(s)")
    return chunks