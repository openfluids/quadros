from __future__ import annotations

import os
from pathlib import Path


def render_snapshots(snapshots: list[Path], config: Path | None, out: Path, *, check: bool = False) -> int:
    """Render one or more Nek snapshots using the extracted legacy renderer."""
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

    return legacy.main([str(path) for path in snapshots])
