# HPC cluster installation notes

`quadros` is not cluster-specific, but it has been validated on large HPC systems. This guide provides typical setup for rendering on a cluster with modular environment and headless rendering requirements.

## Environment setup

Cluster installations typically provide modular Python and FFmpeg. Load your site's modules before creating or activating the project venv. Example using your cluster's module system:

```bash
module purge
module load python/3.11.5  # Your site's Python 3.10+
module load ffmpeg/8.1    # Your site's FFmpeg module (if available)
cd /path/to/work/repos/quadros
. .venv/bin/activate
quadros doctor
```

For reference, on some IDRIS/Jean Zay style systems, the equivalent modules are named `python/3.11.5` and `ffmpeg/8.1`, but module names vary by site.

## Creating the venv

```bash
module purge
module load python/3.11.5  # Load your site's Python
cd /path/to/work/repos/quadros
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

If you intend to use Nek5000 field inspection (recommended), add the optional dependency:

```bash
python -m pip install -e ".[nek5000]"
```

## Validation

Test your setup before running production renders:

```bash
quadros doctor
```

Expected output shows availability of PyVista, pymech (optional, Nek5000-specific), VTK, offscreen rendering, and FFmpeg.

## Rendering workflow

Write render outputs *in loco* (at the case location), not in detached global directories. This is now the default:

```bash
quadros render-many --case-dir /path/to/case --pattern 'snapshot.f*' --config render.json
```

This writes to `/path/to/case/quadros/` unless `--out` is explicitly provided.

Example output structure:

```text
/path/to/case/quadros/
  snapshot_f00001_render_events.jsonl
  snapshot_f00001_render.log
  snapshot_f00001_render_manifest.json
  snapshot_f00001_u_smoke_u_p0p01_qp_comp.png
```

## Slurm execution

The Slurm template `slurm/render_snapshots.sbatch` is generic and site-neutral. Copy it and add your cluster's specific account, partition, and module directives:

```bash
cp slurm/render_snapshots.sbatch render_snapshots_mycluster.sbatch
# Edit to add your cluster details: #SBATCH -A <account>, #SBATCH -p <partition>, module commands
sbatch render_snapshots_mycluster.sbatch
```

The script uses a login shell (`#!/bin/bash -l`) so that module commands are available.

## Headless rendering setup

On compute nodes without a display, set:

```bash
export PYVISTA_OFF_SCREEN=true
```

The `quadros` CLI sets this by default. Verify offscreen rendering works with:

```bash
quadros doctor
```

If `offscreen_render` shows "failed", your VTK/OSMesa installation may need investigation. Check your site's documentation for headless rendering support.
