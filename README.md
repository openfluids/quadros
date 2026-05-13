# neksnap

Private reusable Nek5000 snapshot/frame/video renderer extracted from `myproject/auto_snp`.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

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

## Layout

- `src/neksnap/` — package and CLI wrappers around the extracted renderer.
- `configs/` — JSON render config examples compatible with the original workflow.
- `slurm/render_snapshots.sbatch` — Jean Zay Slurm template.
- `PLAN.md` — source migration plan.
