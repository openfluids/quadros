#!/usr/bin/env bash
#SBATCH -J snp_render
#SBATCH -A vpo@cpu
#SBATCH -p prepost
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=20:00:00
#SBATCH --output=auto_snp/slurm/%x_%j.out
#SBATCH --error=auto_snp/slurm/%x_%j.err

set -euo pipefail

module purge
module load python/3.11.5

CASE_DIR="${CASE_DIR:?set CASE_DIR to the Nek case directory}"
TOOL_DIR="${TOOL_DIR:-"$CASE_DIR/auto_snp"}"
SNAPSHOT_PATTERN="${SNAPSHOT_PATTERN:-sphere0.f[0-9][0-9][0-9][0-9][0-9]}"
RENDER_CONFIG="${RENDER_CONFIG:-"$TOOL_DIR/render_scenes_example.json"}"
FIGURE_DIR="${FIGURE_DIR:-"$TOOL_DIR/figures"}"
PYVISTA_VENV="${PYVISTA_VENV:-/path/to/work/.venvs/auto_snp-pyvista}"

export PYVISTA_VENV
export PYVISTA_FIGURE_DIR="$FIGURE_DIR"
export NEK_RENDER_CONFIG="$RENDER_CONFIG"
export NEK_OBJECT="${NEK_OBJECT:-sphere}"
export NEK_SKIP_MISSING_ISO="${NEK_SKIP_MISSING_ISO:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-$SLURM_CPUS_PER_TASK}"
export PYTHONUNBUFFERED=1
export PYVISTA_OFF_SCREEN=true

mkdir -p "$TOOL_DIR/slurm" "$FIGURE_DIR"

mapfile -t snapshots < <(
    find "$CASE_DIR" -maxdepth 1 -type f -name "$SNAPSHOT_PATTERN" -printf "%p\n" | sort
)

if [[ "${#snapshots[@]}" -eq 0 ]]; then
    echo "error: no snapshots matched $CASE_DIR/$SNAPSHOT_PATTERN" >&2
    exit 2
fi

echo "Render job metadata"
echo "  date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "  hostname=$(hostname)"
echo "  job_id=${SLURM_JOB_ID:-unknown}"
echo "  case_dir=$CASE_DIR"
echo "  tool_dir=$TOOL_DIR"
echo "  render_config=$RENDER_CONFIG"
echo "  figure_dir=$FIGURE_DIR"
echo "  pyvista_venv=$PYVISTA_VENV"
echo "  snapshot_pattern=$SNAPSHOT_PATTERN"
echo "  snapshot_count=${#snapshots[@]}"
printf "  snapshots=%s\n" "${snapshots[*]}"
echo

if [[ ! -x "$TOOL_DIR/render_nek_isosurface_views.sh" ]]; then
    echo "error: missing executable $TOOL_DIR/render_nek_isosurface_views.sh" >&2
    exit 2
fi

if [[ ! -x "$PYVISTA_VENV/bin/python" ]]; then
    echo "error: missing $PYVISTA_VENV/bin/python; run install_pyvista.sh first" >&2
    exit 2
fi

for snapshot in "${snapshots[@]}"; do
    echo "START snapshot $(basename "$snapshot") at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    /usr/bin/time -v "$TOOL_DIR/render_nek_isosurface_views.sh" "$snapshot"
    echo "DONE  snapshot $(basename "$snapshot") at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo
done

echo "Render job finished at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
