# Jean Zay install notes

`neksnap` is not Jean Zay-specific, but this checkout has been validated on Jean Zay under:

```text
/path/to/work/repos/neksnap
```

## Environment

Use the IDRIS Python and FFmpeg modules before activating the project venv:

```bash
module purge
module load python/3.11.5
module load ffmpeg/8.1
cd /path/to/work/repos/neksnap
. .venv/bin/activate
neksnap doctor
```

The venv was created with:

```bash
module purge
module load python/3.11.5
cd /path/to/work/repos/neksnap
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Smoke evidence

A Slurm smoke render on `prepost` rendered one frame from:

```text
/path/to/work/sphere_7/274/sphere0.f00001
```

Output directory:

```text
/path/to/work/neksnap-smoke/sphere_7_274_f00001_u/sphere_7_Re_274
```

Expected smoke artifacts:

```text
sphere0_f00001_render_events.jsonl
sphere0_f00001_render.log
sphere0_f00001_render_manifest.json
sphere0_f00001_u_smoke_u_p0p01_qp_comp.png
```

The Slurm script should use a login shell (`#!/bin/bash -l`) so `module` is available.
