from __future__ import annotations

import argparse
import importlib.util
import shutil
from pathlib import Path

from .encode import encode_frames
from .manifests import inspect_manifest
from .paraview import extract_camera
from .render import render_snapshots


def default_output_dir_for_snapshot(snapshot: Path) -> Path:
    return snapshot.parent / "quadros"


def default_output_dir_for_case(case_dir: Path) -> Path:
    return case_dir / "quadros"


def _has_pymech() -> bool:
    """Whether Nek5000 field inspection is available.

    pymech is an optional extra (`quadros[nek5000]`). find_spec on the top-level
    package is not enough: fields.py imports `pymech.neksuite.field`, and a broken
    or partial install resolves the parent while failing on the submodule.
    """
    try:
        return importlib.util.find_spec("pymech.neksuite.field") is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def doctor(_: argparse.Namespace) -> int:
    checks = {
        "pyvista": importlib.util.find_spec("pyvista") is not None,
        "vtk": importlib.util.find_spec("vtk") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
    }
    # pymech is the `nek5000` extra, not a requirement. Reported so the state is
    # visible, but deliberately excluded from the exit status: an install without
    # it renders every VTK-readable format perfectly well, and failing here would
    # tell a non-Nek user their setup is broken when it is not.
    optional = {"pymech (nek5000 extra)": _has_pymech()}

    for name, ok in checks.items():
        print(f"{name}: {'ok' if ok else 'missing'}")

    # Offscreen rendering smoke: catches broken VTK/OSMesa setups that
    # importlib.find_spec cannot see (e.g. no display + no software rasteriser).
    # _offscreen_render_smoke prints its own line, including the failure reason.
    if checks["pyvista"] and checks["vtk"]:
        checks["offscreen_render"] = _offscreen_render_smoke()

    for name, ok in optional.items():
        print(f"{name}: {'ok' if ok else 'not installed (Nek5000 inspection unavailable)'}")

    return 0 if all(checks.values()) else 1


def _offscreen_render_smoke() -> bool:
    import os
    import tempfile
    os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")
    try:
        import pyvista
        pyvista.OFF_SCREEN = True
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            plotter = pyvista.Plotter(off_screen=True, window_size=(64, 64))
            plotter.add_mesh(pyvista.Sphere())
            plotter.screenshot(tmp_path)
            plotter.close()
            ok = os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        print(f"offscreen_render: {'ok' if ok else 'failed (empty png)'}")
        return ok
    except Exception as exc:
        print(f"offscreen_render: failed ({type(exc).__name__}: {exc})")
        return False


def cmd_render(args: argparse.Namespace) -> int:
    out = args.out or default_output_dir_for_snapshot(args.snapshot)
    return render_snapshots([args.snapshot], args.config, out, check=args.check)


def cmd_render_many(args: argparse.Namespace) -> int:
    snapshots = sorted(args.case_dir.glob(args.pattern))
    out = args.out or default_output_dir_for_case(args.case_dir)
    return render_snapshots(snapshots, args.config, out, check=args.check)


def cmd_inspect(args: argparse.Namespace) -> int:
    print(inspect_manifest(args.manifest))
    return 0


def cmd_encode(args: argparse.Namespace) -> int:
    encode_frames(args.frames, args.out, fps=args.fps, glob=args.glob)
    return 0


def cmd_extract_camera(args: argparse.Namespace) -> int:
    return extract_camera(args.state, args.out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quadros")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check local rendering dependencies")
    p.set_defaults(func=doctor)

    p = sub.add_parser("render", help="render one Nek snapshot")
    p.add_argument("snapshot", type=Path)
    p.add_argument("--config", type=Path)
    p.add_argument("--out", type=Path, help="output root; defaults to SNAPSHOT_PARENT/quadros")
    p.add_argument("--check", action="store_true", help="preflight configured field aliases before rendering")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("render-many", help="render snapshots matched under a case directory")
    p.add_argument("--case-dir", type=Path, required=True)
    p.add_argument("--pattern", required=True)
    p.add_argument("--config", type=Path)
    p.add_argument("--out", type=Path, help="output root; defaults to CASE_DIR/quadros")
    p.add_argument("--check", action="store_true", help="preflight configured field aliases before rendering")
    p.set_defaults(func=cmd_render_many)

    p = sub.add_parser("inspect", help="summarize a render manifest")
    p.add_argument("manifest", type=Path)
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("encode", help="encode PNG frames into a movie with ffmpeg")
    p.add_argument("--frames", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--glob", default="*.png")
    p.set_defaults(func=cmd_encode)

    p = sub.add_parser("extract-camera", help="extract camera JSON from a ParaView .pvsm state")
    p.add_argument("state", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_extract_camera)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
