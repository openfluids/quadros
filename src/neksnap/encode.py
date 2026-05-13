from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _resolve_ffmpeg() -> str:
    """Return an ffmpeg binary path. Prefers ``imageio_ffmpeg`` (which ships
    a static binary inside the venv and is therefore PATH-independent), then
    falls back to whatever ``ffmpeg`` is on PATH.
    """
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return get_ffmpeg_exe()
    except Exception:
        pass
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    raise RuntimeError(
        "no ffmpeg found — install imageio-ffmpeg (pip install imageio-ffmpeg) "
        "or put a system ffmpeg on PATH."
    )


def encode_frames(frames: Path, out: Path, fps: int = 24, glob: str = "*.png") -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = _resolve_ffmpeg()
    cmd = [
        ffmpeg, "-y", "-framerate", str(fps), "-pattern_type", "glob", "-i", str(frames / glob),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
    ]
    subprocess.run(cmd, check=True)
