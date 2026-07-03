"""
CSV loader.

CSV has no page concept, so it's returned as a single unit
(page_number=-1). Rows are flattened into readable "col | col" lines
so the text splitter has natural line boundaries to chunk on, rather
than chunking on raw comma-separated bytes.
"""
import csv


def load_csv(file_path):
    lines = []
    with open(file_path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                lines.append(" | ".join(row))

    text = "\n".join(lines)
    print(f"✅ Extracted {len(text)} characters from CSV ({len(lines)} rows)")
    return [(-1, text)]