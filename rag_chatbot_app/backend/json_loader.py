"""
JSON loader.

Flattens the parsed JSON into readable "path: value" lines instead of
passing raw braces/commas through to chunking, so embeddings capture
meaningful key/value semantics rather than syntax noise.
"""
import json


def load_json(file_path):
    with open(file_path, encoding="utf-8", errors="ignore") as f:
        data = json.load(f)

    text = _flatten(data)
    print(f"✅ Extracted {len(text)} characters from JSON")
    return [(-1, text)]


def _flatten(data, prefix=""):
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            lines.append(_flatten(value, path))
        return "\n".join(lines)

    if isinstance(data, list):
        lines = []
        for i, item in enumerate(data):
            path = f"{prefix}[{i}]"
            lines.append(_flatten(item, path))
        return "\n".join(lines)

    return f"{prefix}: {data}"