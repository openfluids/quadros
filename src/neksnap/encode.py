from __future__ import annotations

import subprocess
from pathlib import Path


def encode_frames(frames: Path, out: Path, fps: int = 24, glob: str = "*.png") -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps), "-pattern_type", "glob", "-i", str(frames / glob),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
    ]
    subprocess.run(cmd, check=True)
