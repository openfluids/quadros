# quadros

`quadros` is a Python CLI package for rendering snapshots into checked frame sets and videos. It can run locally, over SSH, inside containers, or from scheduler jobs without copying scripts into case directories. Nek5000 is the format with dedicated support; other VTK-readable formats are supported via PyVista.

## Features

- Render one snapshot or a globbed case directory of snapshots (Nek5000 with dedicated support).
- Keep JSON render configs compatible with the original `auto_snp` workflow.
- Write manifests, logs, events, frames, and encoded movies under a run output directory.
- Inspect render manifests before deleting dense snapshots.
- Extract camera settings from ParaView `.pvsm` state files.
- Gate NekStab omega-R renders with explicit field aliases and a rebuild hint.

## Install

### With `uv` (recommended for local development)

```bash
git clone https://github.com/openfluids/quadros.git
cd quadros
uv venv .venv
. .venv/bin/activate
uv pip install -e .
quadros doctor
```

For development tools and tests:

```bash
uv pip install -e . --group dev
python -m pytest
```

### With standard `venv` + `pip`

```bash
git clone https://github.com/openfluids/quadros.git
cd quadros
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
quadros doctor
```

For development tools and tests:

```bash
python -m pip install -e . pytest build twine
python -m pytest
```

For a cluster/native rendering setup, see `docs/native-stack.md`.

## CLI

```bash
quadros doctor
quadros render snapshot.f00001 --config configs/render_scenes_example.json
quadros render-many --case-dir /path/to/case --pattern 'sphere0.f*' --config render.json
quadros inspect manifest.json
quadros encode --frames frames/ --out movies/movie.mp4
quadros extract-camera qp_comp.pvsm --out camera.json
```

By default, render outputs are written in loco under `SNAPSHOT_PARENT/quadros` for `render` and `CASE_DIR/quadros` for `render-many`. Use `--out` only when you intentionally want a different output root.

`--check` enables an omega-R preflight gate for configs that declare `field_aliases` for `omR*`/omega fields. If the configured payload is absent, the command points the operator to rebuild the NekStab case with `ifvox = .true.` and `mks <CASE>`.

## Package layout

- `src/quadros/` — importable package and public CLI entrypoint.
- `configs/` — JSON render config examples compatible with the original workflow.
- `slurm/render_snapshots.sbatch` — generic Slurm starter template; copy it and add cluster-specific account, partition, module, or container directives as needed.
- `tests/` — packaging and CLI smoke tests.
- `docs/` — native-stack notes and operating guidance.
- `PLAN.md` — source migration plan.

## Validation

```bash
python -m compileall src tests
python -m quadros --help
quadros doctor
```
