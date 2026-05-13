from __future__ import annotations

import json
from pathlib import Path


def inspect_manifest(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    images = data.get("images", [])
    fields = data.get("available_fields") or data.get("fields") or []
    contours = data.get("isocontours", [])
    return "\n".join([
        f"manifest: {path}",
        f"images: {len(images)}",
        f"contours: {len(contours)}",
        f"available_fields: {fields}",
    ])
