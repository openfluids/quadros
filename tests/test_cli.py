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
    from quadros import fields
    from pathlib import Path

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
    import pytest
    import sys
    from quadros import fields
    from pathlib import Path

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
    from quadros import fields
    from pathlib import Path
    
    assert fields._is_nek_format(Path("case.f00001"))
    assert fields._is_nek_format(Path("/path/to/case/snapshot.f00002"))
    assert not fields._is_nek_format(Path("case.vtu"))
    assert not fields._is_nek_format(Path("case.h5"))


def test_available_field_codes_nek_dispatch(monkeypatch) -> None:
    """available_field_codes should dispatch to Nek reader for .f0NNNN files."""
    from quadros import fields
    from pathlib import Path

    class _FakeHeader:
        variables = "XUP"
        nb_vars = (3, 3, 1, 0, 0)

    monkeypatch.setattr(fields, "_available_field_codes_nek", lambda _p: {"mesh": 3, "velocity": 3, "pressure": 1})
    out = fields.available_field_codes(Path("sphere0.f00001"))
    assert out == {"mesh": 3, "velocity": 3, "pressure": 1}


def test_available_field_codes_degradation_on_missing_pymech(monkeypatch) -> None:
    """available_field_codes should return empty dict if pymech is missing for Nek files."""
    from quadros import fields
    from pathlib import Path

    def _raise_import(_p):
        raise ImportError("No module named 'pymech'")

    monkeypatch.setattr(fields, "_available_field_codes_nek", _raise_import)
    out = fields.available_field_codes(Path("sphere0.f00001"))
    assert out == {}


def test_available_field_codes_vtk_fallback(monkeypatch) -> None:
    """available_field_codes should use pyvista for non-Nek formats."""
    from quadros import fields
    from pathlib import Path

    monkeypatch.setattr(fields, "_available_field_codes_vtk", lambda _p: {"points": 1000, "velocity": 1})
    out = fields.available_field_codes(Path("sphere0.vtu"))
    assert out == {"points": 1000, "velocity": 1}


def test_assert_expected_fields_skips_non_nek_formats(tmp_path, monkeypatch) -> None:
    """assert_expected_fields should skip check for non-Nek formats since omega-R is Nek-specific."""
    from quadros import fields
    import json

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
