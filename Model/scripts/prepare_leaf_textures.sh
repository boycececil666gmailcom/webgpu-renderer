#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXEC="python"

if ! command -v "$PYTHON_EXEC" &> /dev/null; then
    echo "[ERROR] Python is not installed or not in PATH."
    exit 1
fi

echo "[INFO] Running leaf texture preparation pipeline..."
"$PYTHON_EXEC" "${SCRIPT_DIR}/prepare_leaf_textures.py"
echo "[INFO] Leaf texture preparation completed successfully."

