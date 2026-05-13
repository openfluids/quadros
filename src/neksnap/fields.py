from __future__ import annotations

import json
from pathlib import Path


def load_config(config: Path | None) -> dict:
    if config is None:
        return {}
    with config.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def expected_field_aliases(config: Path | None) -> dict[str, str]:
    data = load_config(config)
    aliases = data.get("field_aliases", {})
    return aliases if isinstance(aliases, dict) else {}


def snapshot_header_text(snapshot: Path, max_bytes: int = 4096) -> str:
    with snapshot.open("rb") as handle:
        return handle.read(max_bytes).decode("latin1", errors="ignore")


def assert_expected_fields(snapshot: Path, config: Path | None) -> None:
    """Cheap preflight gate for explicitly configured omega/field aliases.

    Full available/renderable field discovery is recorded by the renderer manifest;
    this check catches the common dense-video failure before a long render starts.
    """
    aliases = expected_field_aliases(config)
    expected = [key for key in aliases if key.lower().startswith("omr") or "omega" in key.lower()]
    if not expected:
        return
    header = snapshot_header_text(snapshot).lower()
    resolved = [aliases[name] for name in expected]
    if not any(alias.lower() in header for alias in resolved):
        raise RuntimeError(
            f"{snapshot}: expected omega-R field alias {resolved!r} was not visible in the snapshot header. "
            "Rebuild the NekStab case with ifvox = .true. and mks <CASE>, then rerun."
        )
