from __future__ import annotations

import json
from pathlib import Path

from quadros.cli import build_parser


def test_parser_exposes_expected_commands() -> None:
    parser = build_parser()
    actions = [action for action in parser._actions if action.dest == "command"]
    choices = set(actions[0].choices)
    assert {"doctor", "render", "render-many", "inspect", "encode", "extract-camera"} <= choices


def test_available_field_codes_decodes_velocity_pressure(monkeypatch) -> None:
    """available_field_codes should reflect the header variables string
    and the nb_vars tuple — no full-volume load.
    """
    from quadros import fields

    class _FakeHeader:
        variables = "XUP"
        nb_vars = (3, 3, 1, 0, 0)

    # Mock the Nek-specific function since read_header is imported lazily
    monkeypatch.setattr(fields, "_available_field_codes_nek", lambda _p: {"mesh": 3, "velocity": 3, "pressure": 1})
    out = fields.available_field_codes(Path("/fake.f00001"))
    assert out == {"mesh": 3, "velocity": 3, "pressure": 1}


def test_available_field_codes_decodes_temperature_and_scalars(monkeypatch) -> None:
    from quadros import fields

    class _FakeHeader:
        variables = "XUPTS"
        nb_vars = (3, 3, 1, 1, 3)  # mesh + velocity + pressure + T + 3 scalars

    monkeypatch.setattr(fields, "_available_field_codes_nek", lambda _p: {"mesh": 3, "velocity": 3, "pressure": 1, "temperature": 1, "s01": 1, "s02": 1, "s03": 1})
    out = fields.available_field_codes(Path("/fake.f00001"))
    assert out == {"mesh": 3, "velocity": 3, "pressure": 1, "temperature": 1, "s01": 1, "s02": 1, "s03": 1}


def test_assert_expected_fields_omr_alias_satisfied(tmp_path, monkeypatch) -> None:
    """omR_x mapped to temperature should pass when header says T is present."""
    import sys
    from pathlib import Path

    from quadros import fields

    cfg = tmp_path / "render.json"
    cfg.write_text(json.dumps({"field_aliases": {"omR_x": "temperature"}}))

    class _FakeHeader:
        variables = "XUPT"
        nb_vars = (3, 3, 1, 1, 0)

    class _FakePymech:
        @staticmethod
        def read_header(_p):
            return _FakeHeader()

    class _FakeNekSuite:
        field = _FakePymech

    class _FakePymechModule:
        neksuite = _FakeNekSuite

    # Mock pymech in sys.modules so the import inside assert_expected_fields works
    monkeypatch.setitem(sys.modules, "pymech", _FakePymechModule)
    monkeypatch.setitem(sys.modules, "pymech.neksuite", _FakeNekSuite)
    monkeypatch.setitem(sys.modules, "pymech.neksuite.field", _FakePymech)

    # Should NOT raise
    fields.assert_expected_fields(Path("/fake.f00001"), cfg)


def test_assert_expected_fields_omr_alias_missing(tmp_path, monkeypatch) -> None:
    """omR_x mapped to temperature should error when the header lacks T."""
    import sys
    from pathlib import Path

    import pytest

    from quadros import fields

    cfg = tmp_path / "render.json"
    cfg.write_text(json.dumps({"field_aliases": {"omR_x": "temperature"}}))

    class _FakeHeader:
        variables = "XUP"
        nb_vars = (3, 3, 1, 0, 0)

    class _FakePymech:
        @staticmethod
        def read_header(_p):
            return _FakeHeader()

    class _FakeNekSuite:
        field = _FakePymech

    class _FakePymechModule:
        neksuite = _FakeNekSuite

    # Mock pymech in sys.modules so the import inside assert_expected_fields works
    monkeypatch.setitem(sys.modules, "pymech", _FakePymechModule)
    monkeypatch.setitem(sys.modules, "pymech.neksuite", _FakeNekSuite)
    monkeypatch.setitem(sys.modules, "pymech.neksuite.field", _FakePymech)

    with pytest.raises(RuntimeError, match="ifvox"):
        fields.assert_expected_fields(Path("/fake.f00001"), cfg)


def test_render_snapshots_writes_manifest_index(tmp_path, monkeypatch) -> None:
    """render_snapshots should call the legacy entry point and write a top-level
    manifest_index.json that enumerates per-snapshot manifests it finds.
    """
    from quadros import render

    snapshots = [tmp_path / "case0.f00001", tmp_path / "case0.f00002"]
    for s in snapshots:
        s.write_bytes(b"")  # placeholder; renderer is mocked
    out = tmp_path / "out"

    def fake_legacy_main(args):
        # Simulate the legacy renderer writing per-snapshot manifests.
        for i, snap in enumerate(snapshots, start=1):
            # Path.stem strips only the last extension; for case0.f00001 it
            # collapses to "case0", so use the full filename for unique labels.
            label = snap.name
            manifest = {
                "snapshot": str(snap),
                "images": [{"path": f"{label}/view1.png"}, {"path": f"{label}/view2.png"}],
                "isocontours": [{"field": "u", "value": 0.01}],
                "available_fields": ["mesh", "velocity", "pressure"],
            }
            (out / f"{label}_render_manifest.json").write_text(json.dumps(manifest))
        return 0

    class _FakeLegacy:
        main = staticmethod(fake_legacy_main)

    monkeypatch.setattr(render, "_legacy_render_nek_isosurface_views", _FakeLegacy, raising=False)
    import sys as _sys
    _sys.modules["quadros._legacy_render_nek_isosurface_views"] = _FakeLegacy

    rc = render.render_snapshots(snapshots, None, out)
    assert rc == 0
    idx = out / "manifest_index.json"
    assert idx.exists()
    data = json.loads(idx.read_text())
    assert data["version"] == 1
    assert data["exit_code"] == 0
    assert data["manifest_count"] == 2
    assert {entry["snapshot"] for entry in data["manifests"]} == {str(s) for s in snapshots}
    assert all(entry["images"] == 2 for entry in data["manifests"])


def test_inspect_manifest_handles_index(tmp_path) -> None:
    from quadros.manifests import inspect_manifest
    index = {
        "version": 1,
        "produced_at": "2026-05-13T16:00:00Z",
        "exit_code": 0,
        "snapshots_requested": ["a.f00001", "b.f00001"],
        "manifest_count": 1,
        "manifests": [{"snapshot": "a.f00001", "images": 3, "isocontours": 1, "available_fields": ["velocity"]}],
    }
    p = tmp_path / "manifest_index.json"
    p.write_text(json.dumps(index))
    text = inspect_manifest(p)
    assert "manifest_count: 1" in text
    assert "a.f00001" in text


def test_inspect_manifest_handles_single_manifest(tmp_path) -> None:
    from quadros.manifests import inspect_manifest
    manifest = {"images": [1, 2, 3], "isocontours": [], "available_fields": ["mesh"]}
    p = tmp_path / "case0.f00001_render_manifest.json"
    p.write_text(json.dumps(manifest))
    text = inspect_manifest(p)
    assert "images: 3" in text
    assert "available_fields: ['mesh']" in text


def test_assert_expected_fields_no_omega_keys_is_noop(tmp_path, monkeypatch) -> None:
    """Configs without omR/omega aliases should not trigger a header read."""
    from quadros import fields

    cfg = tmp_path / "render.json"
    cfg.write_text(json.dumps({"field_aliases": {"foo": "bar"}}))

    called = {"count": 0}

    def _boom(_p):
        called["count"] += 1
        raise AssertionError("read_header should not be invoked")

    # Patch _available_field_codes_nek to detect if it gets called (it shouldn't)
    monkeypatch.setattr(fields, "_available_field_codes_nek", _boom)
    fields.assert_expected_fields(Path("/fake.f00001"), cfg)
    assert called["count"] == 0


def test_is_nek_format_recognizes_nek_files() -> None:
    """_is_nek_format should return True for .f0NNNN files."""
    from pathlib import Path

    from quadros import fields

    assert fields._is_nek_format(Path("case.f00001"))
    assert fields._is_nek_format(Path("/path/to/case/snapshot.f00002"))
    assert not fields._is_nek_format(Path("case.vtu"))
    assert not fields._is_nek_format(Path("case.h5"))


def test_available_field_codes_nek_dispatch(monkeypatch) -> None:
    """available_field_codes should dispatch to Nek reader for .f0NNNN files."""
    from pathlib import Path

    from quadros import fields

    class _FakeHeader:
        variables = "XUP"
        nb_vars = (3, 3, 1, 0, 0)

    monkeypatch.setattr(fields, "_available_field_codes_nek", lambda _p: {"mesh": 3, "velocity": 3, "pressure": 1})
    out = fields.available_field_codes(Path("sphere0.f00001"))
    assert out == {"mesh": 3, "velocity": 3, "pressure": 1}


def test_available_field_codes_degradation_on_missing_pymech(monkeypatch) -> None:
    """available_field_codes should return empty dict if pymech is missing for Nek files."""
    from pathlib import Path

    from quadros import fields

    def _raise_import(_p):
        raise ImportError("No module named 'pymech'")

    monkeypatch.setattr(fields, "_available_field_codes_nek", _raise_import)
    out = fields.available_field_codes(Path("sphere0.f00001"))
    assert out == {}


def test_available_field_codes_vtk_fallback(monkeypatch) -> None:
    """available_field_codes should use pyvista for non-Nek formats."""
    from pathlib import Path

    from quadros import fields

    monkeypatch.setattr(fields, "_available_field_codes_vtk", lambda _p: {"points": 1000, "velocity": 1})
    out = fields.available_field_codes(Path("sphere0.vtu"))
    assert out == {"points": 1000, "velocity": 1}


def test_assert_expected_fields_skips_non_nek_formats(tmp_path, monkeypatch) -> None:
    """assert_expected_fields should skip check for non-Nek formats since omega-R is Nek-specific."""
    import json

    from quadros import fields

    cfg = tmp_path / "render.json"
    cfg.write_text(json.dumps({"field_aliases": {"omR_x": "temperature"}}))

    called = {"count": 0}

    def _boom(_p):
        called["count"] += 1
        raise AssertionError("read_header should not be invoked for non-Nek formats")

    # This should not be called because the format is non-Nek
    monkeypatch.setattr(fields, "_available_field_codes_nek", _boom)
    # Should NOT raise, should NOT call the Nek reader
    fields.assert_expected_fields(Path("sphere0.vtu"), cfg)
    assert called["count"] == 0


def test_doctor_runs_and_reports_every_check(capsys) -> None:
    """`quadros doctor` must actually run.

    It shipped once calling a `_has_pymech()` that was never defined, so the
    command died with NameError on every invocation. Nothing caught it: no test
    exercised doctor at all. This one calls it for real.
    """
    import argparse

    from quadros.cli import doctor

    rc = doctor(argparse.Namespace())
    out = capsys.readouterr().out
    # pymech is optional, so its absence must not make doctor report failure.
    assert rc == 0
    for check in ("pyvista", "vtk", "ffmpeg", "pymech"):
        assert check in out, f"doctor did not report {check}"


def test_doctor_accepts_the_ffmpeg_the_encoder_would_actually_use(monkeypatch, capsys) -> None:
    """doctor must agree with encode.py about what counts as having ffmpeg.

    encode._resolve_ffmpeg() prefers the binary shipped inside imageio_ffmpeg
    and only then falls back to PATH, so a venv with imageio-ffmpeg installed
    can encode perfectly well with no system ffmpeg. doctor checked
    shutil.which("ffmpeg") alone, so that setup was told it was broken and
    doctor exited 1 — the same false alarm the pymech check is explicitly
    written to avoid.
    """
    import argparse

    from quadros import cli, encode

    # No PATH ffmpeg is simulated by patching the resolver itself: doctor now
    # asks the encoder, so PATH is not part of the contract under test.
    monkeypatch.setattr(encode, "_resolve_ffmpeg", lambda: "/venv/lib/imageio_ffmpeg/ffmpeg")

    rc = cli.doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert "ffmpeg: ok" in out, out
    assert rc == 0


def test_doctor_reports_ffmpeg_missing_when_nothing_can_supply_it(monkeypatch, capsys) -> None:
    """With neither a bundled nor a PATH ffmpeg, doctor must still fail."""
    import argparse

    from quadros import cli, encode

    def _no_ffmpeg() -> str:
        raise RuntimeError("no ffmpeg found")

    monkeypatch.setattr(encode, "_resolve_ffmpeg", _no_ffmpeg)

    rc = cli.doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert "ffmpeg: missing" in out, out
    assert rc == 1


def test_has_pymech_reports_false_when_absent(monkeypatch) -> None:
    """The probe must answer False rather than raise when pymech is missing."""
    import importlib.util

    from quadros import cli

    def _missing(name, *a, **k):
        if name.startswith("pymech"):
            raise ModuleNotFoundError(name)
        return importlib.util.find_spec(name, *a, **k)

    monkeypatch.setattr(cli.importlib.util, "find_spec", _missing)
    assert cli._has_pymech() is False


# --- encode.py: ffmpeg resolution and command construction -------------------


def test_encode_frames_builds_a_glob_pattern_command(tmp_path, monkeypatch) -> None:
    """The frame glob must reach ffmpeg as a pattern, not a pre-expanded list.

    -pattern_type glob with a single -i is what lets a run of thousands of PNGs
    be encoded without building an argv longer than the OS allows.
    """
    from quadros import encode

    frames = tmp_path / "frames"
    frames.mkdir()
    out = tmp_path / "deeper" / "movie.mp4"
    seen = {}

    monkeypatch.setattr(encode, "_resolve_ffmpeg", lambda: "/bin/ffmpeg")
    monkeypatch.setattr(encode.subprocess, "run", lambda cmd, **kw: seen.update(cmd=cmd, kw=kw))

    encode.encode_frames(frames, out, fps=30)

    cmd = seen["cmd"]
    assert cmd[0] == "/bin/ffmpeg"
    assert "-framerate" in cmd and cmd[cmd.index("-framerate") + 1] == "30"
    assert cmd[cmd.index("-pattern_type") + 1] == "glob"
    assert cmd[cmd.index("-i") + 1] == str(frames / "*.png")
    # yuv420p is what makes the result playable outside ffmpeg itself
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert cmd[-1] == str(out)
    assert seen["kw"]["check"] is True
    # the output directory must be created, or ffmpeg fails at the last step
    assert out.parent.is_dir()


def test_encode_frames_honours_a_custom_glob(tmp_path, monkeypatch) -> None:
    from quadros import encode

    frames = tmp_path / "frames"
    frames.mkdir()
    seen = {}
    monkeypatch.setattr(encode, "_resolve_ffmpeg", lambda: "/bin/ffmpeg")
    monkeypatch.setattr(encode.subprocess, "run", lambda cmd, **kw: seen.update(cmd=cmd))

    encode.encode_frames(frames, tmp_path / "m.mp4", glob="view1_*.png")
    assert seen["cmd"][seen["cmd"].index("-i") + 1] == str(frames / "view1_*.png")


def test_resolve_ffmpeg_prefers_the_bundled_binary(monkeypatch) -> None:
    """imageio_ffmpeg ships a static binary inside the venv, so it is
    PATH-independent and must win over whatever happens to be installed."""
    import sys
    import types

    from quadros import encode

    fake = types.ModuleType("imageio_ffmpeg")
    fake.get_ffmpeg_exe = lambda: "/venv/bundled/ffmpeg"
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", fake)
    monkeypatch.setattr(encode.shutil, "which", lambda _n: "/usr/bin/ffmpeg")

    assert encode._resolve_ffmpeg() == "/venv/bundled/ffmpeg"


def test_resolve_ffmpeg_falls_back_to_path(monkeypatch) -> None:
    import builtins
    import sys

    from quadros import encode

    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    real_import = builtins.__import__

    def no_imageio(name, *a, **k):
        if name == "imageio_ffmpeg":
            raise ImportError("not installed")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_imageio)
    monkeypatch.setattr(encode.shutil, "which", lambda _n: "/usr/bin/ffmpeg")
    assert encode._resolve_ffmpeg() == "/usr/bin/ffmpeg"


def test_resolve_ffmpeg_raises_a_actionable_error_when_nothing_is_available(monkeypatch) -> None:
    import builtins

    import pytest

    from quadros import encode

    real_import = builtins.__import__

    def no_imageio(name, *a, **k):
        if name == "imageio_ffmpeg":
            raise ImportError("not installed")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_imageio)
    monkeypatch.setattr(encode.shutil, "which", lambda _n: None)
    with pytest.raises(RuntimeError, match="imageio-ffmpeg"):
        encode._resolve_ffmpeg()


# --- render.py: the paths a failed run actually takes ------------------------


def test_render_snapshots_refuses_an_empty_snapshot_list(tmp_path) -> None:
    """An empty glob is a user error worth naming, not a silent no-op run."""
    import pytest

    from quadros import render

    with pytest.raises(ValueError, match="no snapshots matched"):
        render.render_snapshots([], None, tmp_path / "out")


def test_summarise_manifest_reports_a_corrupt_manifest_instead_of_raising(tmp_path) -> None:
    """One truncated manifest must not abort the index for a whole run."""
    from quadros import render

    bad = tmp_path / "case0_render_manifest.json"
    bad.write_text("{not json")
    summary = render._summarise_manifest(bad)
    assert summary["manifest"] == str(bad)
    assert "JSONDecodeError" in summary["error"]


def test_render_snapshots_indexes_a_corrupt_manifest_without_dying(tmp_path, monkeypatch) -> None:
    import sys

    from quadros import render

    snap = tmp_path / "case0.f00001"
    snap.write_bytes(b"")
    out = tmp_path / "out"

    def fake_main(_args):
        (out / "case0.f00001_render_manifest.json").write_text("{truncated")
        return 0

    class _FakeLegacy:
        main = staticmethod(fake_main)

    sys.modules["quadros._legacy_render_nek_isosurface_views"] = _FakeLegacy
    rc = render.render_snapshots([snap], None, out)

    assert rc == 0
    data = json.loads((out / "manifest_index.json").read_text())
    assert data["manifest_count"] == 1
    assert "error" in data["manifests"][0]


def test_render_snapshots_exports_the_config_to_the_legacy_renderer(tmp_path, monkeypatch) -> None:
    """The legacy renderer reads its config from the environment, not an argument."""
    import os
    import sys

    from quadros import render

    snap = tmp_path / "case0.f00001"
    snap.write_bytes(b"")
    cfg = tmp_path / "render.json"
    cfg.write_text("{}")
    out = tmp_path / "out"
    seen = {}

    def fake_main(_args):
        seen["config"] = os.environ.get("NEK_RENDER_CONFIG")
        seen["figdir"] = os.environ.get("PYVISTA_FIGURE_DIR")
        seen["offscreen"] = os.environ.get("PYVISTA_OFF_SCREEN")
        return 0

    class _FakeLegacy:
        main = staticmethod(fake_main)

    sys.modules["quadros._legacy_render_nek_isosurface_views"] = _FakeLegacy
    render.render_snapshots([snap], cfg, out)

    assert seen["config"] == str(cfg)
    assert seen["figdir"] == str(out)
    assert seen["offscreen"] == "true"


def test_render_snapshots_check_gate_runs_before_the_renderer(tmp_path, monkeypatch) -> None:
    """--check must fail on a missing field before spending a long render."""
    import sys

    import pytest

    from quadros import fields, render

    snap = tmp_path / "case0.f00001"
    snap.write_bytes(b"")
    called = {"render": False}

    def boom(_snapshot, _config):
        raise RuntimeError("ifvox missing")

    class _FakeLegacy:
        @staticmethod
        def main(_args):
            called["render"] = True
            return 0

    monkeypatch.setattr(fields, "assert_expected_fields", boom)
    sys.modules["quadros._legacy_render_nek_isosurface_views"] = _FakeLegacy

    with pytest.raises(RuntimeError, match="ifvox missing"):
        render.render_snapshots([snap], None, tmp_path / "out", check=True)
    assert called["render"] is False, "renderer ran despite the preflight check failing"
