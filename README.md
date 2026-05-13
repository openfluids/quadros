# neksnap

`neksnap` is a private Python CLI package for rendering Nek5000 snapshots into checked frame sets and videos. It extracts the reusable `auto_snp` workflow from `myproject` into an installable package that can run locally or from a Slurm job without copying scripts into case directories.

## Features

- Render one snapshot or a globbed case directory of snapshots.
- Keep JSON render configs compatible with the original `auto_snp` workflow.
- Write manifests, logs, events, frames, and encoded movies under a run output directory.
- Inspect render manifests before deleting dense snapshots.
- Extract camera settings from ParaView `.pvsm` state files.
- Gate NekStab omega-R renders with explicit field aliases and a rebuild hint.

## Install for development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

For a cluster/native rendering setup, see `docs/native-stack.md`.

## CLI

```bash
neksnap doctor
neksnap render snapshot.f00001 --config configs/render_scenes_example.json --out frames/
neksnap render-many --case-dir /path/to/case --pattern 'sphere0.f*' --config render.json --out frames/
neksnap inspect manifest.json
neksnap encode --frames frames/ --out movies/movie.mp4
neksnap extract-camera qp_comp.pvsm --out camera.json
```

`--check` enables an omega-R preflight gate for configs that declare `field_aliases` for `omR*`/omega fields. If the configured payload is absent, the command points the operator to rebuild the NekStab case with `ifvox = .true.` and `mks <CASE>`.

## Package layout

- `src/neksnap/` — importable package and public CLI entrypoint.
- `configs/` — JSON render config examples compatible with the original workflow.
- `slurm/render_snapshots.sbatch` — current Slurm template for a Jean Zay job; it is only a starting point and `neksnap` is not limited to Jean Zay.
- `tests/` — packaging and CLI smoke tests.
- `docs/` — native-stack notes and operating guidance.
- `PLAN.md` — source migration plan.

## Validation

```bash
python -m compileall src tests
python -m neksnap --help
neksnap doctor
```
