"""Snapshot field inspection — Nek5000/NekStab binary headers via pymech.

The Nek5000 binary `.f0NNNN` format carries a fixed header that names the
included variables with a single-letter code (X=mesh, U=velocity, P=pressure,
T=temperature, S=scalars) plus a `nb_vars` tuple counting each category.
`pymech.neksuite.field.read_header` reads just the header (no full-volume
load) — fast enough to use as a preflight gate before a long render.

Other VTK-readable formats (.vtu, .vtk, .xdmf, .exo, .cgns) are probed with
`pyvista.read()` without dedicated field inspection.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterator


def load_config(config: Path | None) -> dict:
    if config is None:
        return {}
    with config.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def expected_field_aliases(config: Path | None) -> dict[str, str]:
    data = load_config(config)
    aliases = data.get("field_aliases", {})
    return aliases if isinstance(aliases, dict) else {}


def _decode_header(header) -> dict[str, int]:
    var_str = header.variables.upper()
    nb_vars = header.nb_vars
    out: dict[str, int] = {}
    if "X" in var_str:
        out["mesh"] = int(nb_vars[0])
    if "U" in var_str:
        out["velocity"] = int(nb_vars[1])
    if "P" in var_str:
        out["pressure"] = int(nb_vars[2])
    if "T" in var_str:
        out["temperature"] = int(nb_vars[3])
    n_scalars = int(nb_vars[4]) if len(nb_vars) > 4 else 0
    for i in range(1, n_scalars + 1):
        out[f"s{i:02d}"] = 1
    return out


def _is_nek_format(snapshot: Path) -> bool:
    """Check if snapshot is a Nek5000 binary file by extension."""
    name = snapshot.name
    # Nek binary files: .f00000 through .f99999 (e.g., sphere0.f00001)
    # Check if filename contains ".f" followed by 5 digits
    import re
    return bool(re.search(r'\.f\d{5}$', name))


def _available_field_codes_nek(snapshot: Path) -> dict[str, int]:
    """Read Nek5000 snapshot binary header and decode field codes."""
    from pymech.neksuite.field import read_header
    return _decode_header(read_header(snapshot))


def _available_field_codes_vtk(snapshot: Path) -> dict[str, int]:
    """Probe a VTK-readable file with PyVista and report available arrays.

    VTK writes parse failures straight to its own C++ console, which buries the
    one line the user needs. Silence it for the duration of the probe and report
    the failure ourselves instead.
    """
    import pyvista
    from vtkmodules.vtkCommonCore import vtkObject

    was_on = vtkObject.GetGlobalWarningDisplay()
    vtkObject.GlobalWarningDisplayOff()
    try:
        mesh = pyvista.read(str(snapshot))
    except Exception as exc:
        # Preflight is advisory: the renderer may still cope, so do not abort.
        print(
            f"quadros: cannot inspect {snapshot.name} ({type(exc).__name__}); "
            f"skipping preflight field check",
            file=sys.stderr,
        )
        return {}
    finally:
        if was_on:
            vtkObject.GlobalWarningDisplayOn()

    out: dict[str, int] = {}
    if mesh.n_points > 0:
        out["points"] = mesh.n_points
    if mesh.n_cells > 0:
        out["cells"] = mesh.n_cells
    for name in mesh.array_names:
        out[name] = 1
    return out


def available_field_codes(snapshot: Path) -> dict[str, int]:
    """Return {alias_lowercase: count} for fields actually present in the
    snapshot. For Nek5000 binary files (.f0NNNN), reads the binary header.
    For other VTK-readable formats, probes with pyvista.read().
    Returns empty dict if format is unrecognised or probe fails.
    """
    if _is_nek_format(snapshot):
        try:
            return _available_field_codes_nek(snapshot)
        except (ImportError, ModuleNotFoundError):
            print(
                f"quadros: {snapshot.name} is a Nek5000 file but pymech is not "
                f"installed; skipping preflight field check. Install with "
                f"'pip install quadros[nek5000]'.",
                file=sys.stderr,
            )
            return {}
    else:
        return _available_field_codes_vtk(snapshot)


def _omega_alias_targets(aliases: dict[str, str]) -> Iterator[tuple[str, str]]:
    for key, target in aliases.items():
        if key.lower().startswith("omr") or "omega" in key.lower():
            yield key, target


def assert_expected_fields(snapshot: Path, config: Path | None) -> None:
    """Preflight gate for omega-R style alias mappings.

    For Nek5000 files, reads the snapshot binary header (no full-volume load)
    and asserts that every alias declared under `field_aliases` for an
    omega-R / omega field actually exists in the file. Targets may be
    'velocity', 'pressure', 'temperature' or 'sNN' (scalar index).

    For other formats, this check is skipped (omega-R is Nek5000-specific).

    Raises ``RuntimeError`` with a rebuild hint if any expected field is
    missing from a Nek5000 file.
    """
    aliases = expected_field_aliases(config)
    needed = list(_omega_alias_targets(aliases))
    if not needed:
        return

    # Omega-R fields are Nek5000-specific; skip check for other formats
    if not _is_nek_format(snapshot):
        return

    try:
        from pymech.neksuite.field import read_header
        header = read_header(snapshot)
    except (ImportError, ModuleNotFoundError):
        # pymech not available; cannot check Nek5000 format
        return

    available = _decode_header(header)
    missing = [(key, target) for key, target in needed if available.get(target.lower(), 0) <= 0]
    if missing:
        details = ", ".join(f"{k} -> {t!r}" for k, t in missing)
        raise RuntimeError(
            f"{snapshot}: configured omega-R field aliases not in header: {details}. "
            "Rebuild the NekStab case with ifvox = .true. and mks <CASE>, then rerun. "
            f"Header shows variables={header.variables!r}, nb_vars={header.nb_vars}."
        )
