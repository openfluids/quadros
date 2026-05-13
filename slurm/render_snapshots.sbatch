#!/usr/bin/env bash
#SBATCH -J neksnap_render
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=20:00:00
#SBATCH --output=neksnap-slurm/%x_%j.out
#SBATCH --error=neksnap-slurm/%x_%j.err

# Generic Slurm template for neksnap. Copy this file and add site-specific
# directives such as account, partition/QoS, modules, or container setup.
# Example site-specific directives that may be needed on some clusters:
#   #SBATCH -A <account>
#   #SBATCH -p <partition>
#   module purge && module load python/3.11

set -euo pipefail

CASE_DIR="${CASE_DIR:?set CASE_DIR to the Nek case directory}"
SNAPSHOT_PATTERN="${SNAPSHOT_PATTERN:-*.f[0-9][0-9][0-9][0-9][0-9]}"
RENDER_CONFIG="${RENDER_CONFIG:?set RENDER_CONFIG to a neksnap JSON render config}"
OUT_DIR="${OUT_DIR:-$CASE_DIR/neksnap}"
NEKSNAP_BIN="${NEKSNAP_BIN:-neksnap}"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-${SLURM_CPUS_PER_TASK:-1}}"
export PYTHONUNBUFFERED=1
export PYVISTA_OFF_SCREEN="${PYVISTA_OFF_SCREEN:-true}"

mkdir -p "$OUT_DIR" "$OUT_DIR/slurm"

echo "neksnap Slurm render job"
echo "  date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "  hostname=$(hostname)"
echo "  job_id=${SLURM_JOB_ID:-unknown}"
echo "  case_dir=$CASE_DIR"
echo "  snapshot_pattern=$SNAPSHOT_PATTERN"
echo "  render_config=$RENDER_CONFIG"
echo "  out_dir=$OUT_DIR"
echo "  neksnap_bin=$NEKSNAP_BIN"
echo

"$NEKSNAP_BIN" doctor
"$NEKSNAP_BIN" render-many \
  --case-dir "$CASE_DIR" \
  --pattern "$SNAPSHOT_PATTERN" \
  --config "$RENDER_CONFIG" \
  --out "$OUT_DIR" \
  ${NEKSNAP_RENDER_CHECK:+--check}

echo "neksnap Slurm render finished at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
