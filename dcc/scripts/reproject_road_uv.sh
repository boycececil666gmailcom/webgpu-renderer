#!/usr/bin/env bash
#region Scaffolding
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BLENDER_PATH="/c/Program Files/Blender Foundation/Blender 5.0/blender.exe"
BLEND_FILE="${PROJECT_ROOT}/dcc/asset.blend"
PYTHON_SCRIPT="${SCRIPT_DIR}/reproject_road_uv.py"
#endregion

#region Main
echo "[Runner] Running road UV reprojection in Blender..."
if [ -f "${BLENDER_PATH}" ]; then
    "${BLENDER_PATH}" -b "${BLEND_FILE}" --python "${PYTHON_SCRIPT}"
else
    blender -b "${BLEND_FILE}" --python "${PYTHON_SCRIPT}"
fi
echo "[Runner] Finished road UV reprojection."
#endregion
