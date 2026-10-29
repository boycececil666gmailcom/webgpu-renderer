#!/usr/bin/env bash
set -euo pipefail

# #region Scaffolding
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BLENDER_BIN="C:/Program Files/Blender Foundation/Blender 5.0/blender.exe"
BLEND_FILE="$REPO_ROOT/Model/asset.blend"
PYTHON_SCRIPT="$SCRIPT_DIR/generate_tree_lods_no_decimate.py"
# #endregion

# #region Core
echo "==> Running Tree LOD generation without bark decimation..."
"$BLENDER_BIN" -b "$BLEND_FILE" --python "$PYTHON_SCRIPT"
echo "==> Tree LOD generation completed successfully."
# #endregion
