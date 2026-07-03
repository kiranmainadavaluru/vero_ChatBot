"""
XML loader.

Walks the element tree and pulls out visible text content, dropping
tags and attributes. No page concept, so returned as a single unit
(page_number=-1).
"""
import xml.etree.ElementTree as ET


def load_xml(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()

    lines = [elem.text.strip() for elem in root.iter() if elem.text and elem.text.strip()]
    text = "\n".join(lines)

    print(f"✅ Extracted {len(text)} characters from XML")
    return [(-1, text)]