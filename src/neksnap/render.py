"""Snapshot rendering — thin coordinator around the legacy isosurface renderer.

The legacy renderer (`_legacy_render_nek_isosurface_views.py`) already writes a
per-snapshot output contract under the run directory:

    <out>/
      <snap_label>_render_manifest.json   # scenes, images, isocontours, timings
      <snap_label>_render_events.jsonl    # one JSON event per render phase
      <snap_label>_*.log                  # human-readable run log
      <snap_label>/<scene>/<view>.png     # frame images (or flat <snap>.png)

This module just routes snapshot paths into the legacy entry point and adds a
top-level ``manifest_index.json`` that enumerates the per-snapshot manifests
produced by the run so downstream tools (``neksnap inspect``, the cockpit
sync step, beads) can iterate without re-globbing.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _discover_per_snapshot_manifests(out: Path) -> list[Path]:
    return sorted(out.rglob("*_render_manifest.json"))


def _summarise_manifest(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return {"manifest": str(path), "error": f"{type(exc).__name__}: {exc}"}
    return {
        "manifest": str(path),
        "snapshot": data.get("snapshot") or data.get("input") or data.get("source"),
        "images": len(data.get("images", [])),
        "isocontours": len(data.get("isocontours", [])),
        "available_fields": data.get("available_fields") or data.get("fields"),
    }


def _write_index(out: Path, snapshots: list[Path], rc: int) -> Path:
    manifests = _discover_per_snapshot_manifests(out)
    index = {
        "version": 1,
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "exit_code": rc,
        "snapshots_requested": [str(p) for p in snapshots],
        "manifest_count": len(manifests),
        "manifests": [_summarise_manifest(p) for p in manifests],
    }
    path = out / "manifest_index.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2, sort_keys=False)
    return path


def render_snapshots(snapshots: list[Path], config: Path | None, out: Path, *, check: bool = False) -> int:
    """Render one or more Nek snapshots using the legacy renderer and write a
    ``manifest_index.json`` summarising the per-snapshot manifests produced.

    Returns the exit code from the legacy renderer (0 on success).
    """
    if not snapshots:
        raise ValueError("no snapshots matched")
    out.mkdir(parents=True, exist_ok=True)
    os.environ["PYVISTA_FIGURE_DIR"] = str(out)
    if config is not None:
        os.environ["NEK_RENDER_CONFIG"] = str(config)
    os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")

    if check:
        from .fields import assert_expected_fields

        for snapshot in snapshots:
            assert_expected_fields(snapshot, config)

    from . import _legacy_render_nek_isosurface_views as legacy

    rc = legacy.main([str(path) for path in snapshots])
    _write_index(out, snapshots, rc)
    return rc
