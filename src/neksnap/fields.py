"""Snapshot field inspection — Nek5000/NekStab binary headers via pymech.

The Nek5000 binary `.f0NNNN` format carries a fixed header that names the
included variables with a single-letter code (X=mesh, U=velocity, P=pressure,
T=temperature, S=scalars) plus a `nb_vars` tuple counting each category.
`pymech.neksuite.field.read_header` reads just the header (no full-volume
load) — fast enough to use as a preflight gate before a long render.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from pymech.neksuite.field import read_header


def load_config(config: Path | None) -> dict:
    if config is None:
        return {}
    with config.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def expected_field_aliases(config: Path | None) -> dict[str, str]:
    data = load_config(config)
    aliases = data.get("field_aliases", {})
    return aliases if isinstance(aliases, dict) else {}


def available_field_codes(snapshot: Path) -> dict[str, int]:
    """Return {alias_lowercase: count} for fields actually present in the
    snapshot binary header. Recognised aliases: mesh, velocity, pressure,
    temperature, s01, s02, ... (count >= 1 means present).
    """
    header = read_header(snapshot)
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


def _omega_alias_targets(aliases: dict[str, str]) -> Iterator[tuple[str, str]]:
    for key, target in aliases.items():
        if key.lower().startswith("omr") or "omega" in key.lower():
            yield key, target


def assert_expected_fields(snapshot: Path, config: Path | None) -> None:
    """Preflight gate for omega-R style alias mappings.

    Reads the snapshot binary header (no full-volume load) and asserts that
    every alias declared under `field_aliases` for an omega-R / omega field
    actually exists in the file. Targets may be 'velocity', 'pressure',
    'temperature' or 'sNN' (scalar index). Raises ``RuntimeError`` with a
    rebuild hint if any expected field is missing.
    """
    aliases = expected_field_aliases(config)
    needed = list(_omega_alias_targets(aliases))
    if not needed:
        return
    available = available_field_codes(snapshot)
    missing = [(key, target) for key, target in needed if available.get(target.lower(), 0) <= 0]
    if missing:
        details = ", ".join(f"{k} -> {t!r}" for k, t in missing)
        header = read_header(snapshot)
        raise RuntimeError(
            f"{snapshot}: configured omega-R field aliases not in header: {details}. "
            "Rebuild the NekStab case with ifvox = .true. and mks <CASE>, then rerun. "
            f"Header shows variables={header.variables!r}, nb_vars={header.nb_vars}."
        )
