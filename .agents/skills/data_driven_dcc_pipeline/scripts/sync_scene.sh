#!/usr/bin/env bash
#region Imports
# Core Bash environment settings
set -euo pipefail
export MSYS2_ARG_CONV_EXCL="/sdcard"
#endregion

#region Types
# Configuration variables
PACKAGE="org.antigravity.webgpurenderer"
ACTIVITY="android.app.NativeActivity"
REMOTE_DIR="/sdcard/Android/data/${PACKAGE}/files"
REMOTE_GLB="${REMOTE_DIR}/base_scene.glb"
#endregion

#region Scaffolding
log_info() {
    echo -e "\033[1;36m[DCC-Sync]\033[0m $1"
}

log_success() {
    echo -e "\033[1;32m[DCC-Sync]\033[0m $1"
}

get_target_serial() {
    adb devices | grep -E '^[a-zA-Z0-9._-]+[[:space:]]+device' | head -n 1 | awk '{print $1}'
}
#endregion

#region Transfer
push_asset() {
    local serial="$1"
    local local_glb="$2"
    log_info "Pushing ${local_glb} to device (${serial})..."
    adb -s "$serial" shell mkdir -p "$REMOTE_DIR" >/dev/null 2>&1 || true
    adb -s "$serial" push "$local_glb" "$REMOTE_GLB"
    log_success "Asset transferred successfully."
}

reload_application() {
    local serial="$1"
    log_info "Restarting ${ACTIVITY} on target device..."
    adb -s "$serial" shell am force-stop "$PACKAGE" >/dev/null 2>&1 || true
    adb -s "$serial" shell am start -n "${PACKAGE}/${ACTIVITY}" >/dev/null 2>&1 || true
    log_success "NativeActivity reloaded."
}

capture_frame() {
    local serial="$1"
    local output_img="$2"
    log_info "Waiting for engine initialization and GLB loading (12s)..."
    sleep 12
    adb -s "$serial" exec-out screencap -p > "$output_img"
    log_success "Saved verification capture to ${output_img}"
}
#endregion

#region Core
orchestrate_sync() {
    local serial="$1"
    local local_glb="$2"
    local output_img="$3"

    push_asset "$serial" "$local_glb"
    reload_application "$serial"
    capture_frame "$serial" "$output_img"
}
#endregion

#region Main
main() {
    local script_dir; script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local project_root
    project_root="$(git -C "${script_dir}" rev-parse --show-toplevel 2>/dev/null || (cd "${script_dir}/../../../.." && pwd))"
    local local_glb="${project_root}/assets/models/base_scene.glb"
    local output_img="${project_root}/live_sync.png"

    if [[ ! -f "$local_glb" ]]; then
        echo "Error: GLB file not found at ${local_glb}" >&2
        exit 1
    fi

    local serial; serial="$(get_target_serial)"
    if [[ -z "$serial" ]]; then
        echo "Error: No connected ADB device or emulator found." >&2
        exit 1
    fi

    orchestrate_sync "$serial" "$local_glb" "$output_img"
    log_success "DCC sync roundtrip complete."
}

main "$@"
#endregion
