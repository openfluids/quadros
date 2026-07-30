from __future__ import annotations

import json
from pathlib import Path


def inspect_manifest(path: Path) -> str:
    """Summarise a render manifest. Accepts either a per-snapshot
    ``*_render_manifest.json`` written by the legacy renderer, or the top-level
    ``manifest_index.json`` written by ``render_snapshots``.
    """
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if isinstance(data, dict) and data.get("manifest_count") is not None:
        lines = [
            f"index: {path}",
            f"produced_at: {data.get('produced_at')}",
            f"exit_code: {data.get('exit_code')}",
            f"snapshots_requested: {len(data.get('snapshots_requested', []))}",
            f"manifest_count: {data.get('manifest_count')}",
        ]
        for entry in data.get("manifests", []):
            snap = entry.get("snapshot") or "?"
            lines.append(
                f"  - {snap}: images={entry.get('images', 0)}, "
                f"contours={entry.get('isocontours', 0)}, "
                f"fields={entry.get('available_fields') or []}"
            )
        return "\n".join(lines)

    images = data.get("images", [])
    fields = data.get("available_fields") or data.get("fields") or []
    contours = data.get("isocontours", [])
    return "\n".join([
        f"manifest: {path}",
        f"images: {len(images)}",
        f"contours: {len(contours)}",
        f"available_fields: {fields}",
    ])
