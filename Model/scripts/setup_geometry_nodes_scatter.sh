#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLENDER_EXEC="C:/Program Files/Blender Foundation/Blender 5.0/blender.exe"
BLEND_FILE="$(dirname "$SCRIPT_DIR")/asset.blend"

if [ ! -f "$BLENDER_EXEC" ]; then
    echo "[ERROR] Blender executable not found at: $BLENDER_EXEC"
    exit 1
fi

if [ ! -f "$BLEND_FILE" ]; then
    echo "[ERROR] Blend file not found at: $BLEND_FILE"
    exit 1
fi

echo "[INFO] Running Geometry Nodes leaf scatter setup..."
"$BLENDER_EXEC" -b "$BLEND_FILE" -P "${SCRIPT_DIR}/setup_geometry_nodes_scatter.py"
echo "[INFO] Scatter setup completed successfully."

