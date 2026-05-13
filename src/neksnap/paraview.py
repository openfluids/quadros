from __future__ import annotations

import sys
from pathlib import Path


def extract_camera(state: Path, out: Path) -> int:
    from . import _legacy_extract_paraview_state as legacy

    old_argv = sys.argv[:]
    try:
        sys.argv = ["neksnap extract-camera", str(state), "--camera-json", str(out)]
        return legacy.main()
    finally:
        sys.argv = old_argv
