#!/usr/bin/env bash
#region Config
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

mkdir -p "$LOG_DIR"

MODE="run"
BUILD_PROFILE="debug"
MODEL_PATH=""
DETACH=false
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -b|--build)
            MODE="build"
            shift
            ;;
        -r|--run)
            MODE="run"
            shift
            ;;
        -t|--test)
            MODE="test"
            shift
            ;;
        -d|--detach)
            DETACH=true
            shift
            ;;
        --release)
            BUILD_PROFILE="release"
            shift
            ;;
        --debug)
            BUILD_PROFILE="debug"
            shift
            ;;
        -m|--model)
            MODEL_PATH="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: ./windows/run.sh [OPTIONS] [-- MODEL_PATH]"
            echo ""
            echo "Options:"
            echo "  -r, --run        Run the desktop WebGPU viewer in foreground (default)"
            echo "  -d, --detach     Spawn independent foreground window & free terminal"
            echo "  -b, --build      Build the desktop binary only"
            echo "  -t, --test       Run host unit & integration tests"
            echo "  --release        Build/run in release mode"
            echo "  --debug          Build/run in debug mode (default)"
            echo "  -m, --model PATH Pass specific glTF/GLB model path"
            echo "  -h, --help       Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./windows/run.sh"
            echo "  ./windows/run.sh -d"
            echo "  ./windows/run.sh --release"
            echo "  ./windows/run.sh -m gltf/tree_01_lod1.glb"
            echo "  ./windows/run.sh -t"
            exit 0
            ;;
        --)
            shift
            EXTRA_ARGS+=("$@")
            break
            ;;
        *)
            if [[ -z "$MODEL_PATH" && "$1" != -* ]]; then
                MODEL_PATH="$1"
                shift
            else
                EXTRA_ARGS+=("$1")
                shift
            fi
            ;;
    esac
done

CARGO_DIR="${CARGO_HOME:-${USERPROFILE:-$HOME}/.cargo}"
CARGO_BIN="${CARGO_DIR}/bin/cargo.exe"
if [[ ! -x "$CARGO_BIN" ]]; then
    CARGO_BIN="cargo"
fi

TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
RUN_LOG="$LOG_DIR/run_${TIMESTAMP}.log"
LATEST_LOG="$LOG_DIR/latest.log"
#endregion

#region Scaffolding
log() {
    local level="$1"
    local message="$2"
    echo "[Windows-CI] [${level}] ${message}" | tee -a "$RUN_LOG"
}

finalize_logs() {
    cp -f "$RUN_LOG" "$LATEST_LOG" 2>/dev/null || true
    log "INFO" "Log saved to: $RUN_LOG"
}
trap finalize_logs EXIT
#endregion

#region Core
build_binary() {
    log "INFO" "Building webgpu-viewer binary (profile: $BUILD_PROFILE)..."
    local flags=(build --bin webgpu-viewer)
    if [[ "$BUILD_PROFILE" == "release" ]]; then
        flags+=(--release)
    fi

    cd "$PROJECT_ROOT"
    "$CARGO_BIN" "${flags[@]}" 2>&1 | tee -a "$RUN_LOG"
}

run_tests() {
    log "INFO" "Executing host unit & integration tests..."
    cd "$PROJECT_ROOT"
    "$CARGO_BIN" test --target x86_64-pc-windows-gnullvm 2>&1 | tee -a "$RUN_LOG"
}

launch_viewer() {
    log "INFO" "Launching desktop WebGPU viewer (profile: $BUILD_PROFILE)..."
    local flags=(run --bin webgpu-viewer)
    if [[ "$BUILD_PROFILE" == "release" ]]; then
        flags+=(--release)
    fi

    local run_args=()
    if [[ -n "$MODEL_PATH" ]]; then
        run_args+=("$MODEL_PATH")
    fi
    if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
        run_args+=("${EXTRA_ARGS[@]}")
    fi

    cd "$PROJECT_ROOT"
    if [[ "$DETACH" == true ]]; then
        log "INFO" "Spawning WebGPU viewer in independent foreground window..."
        if [[ ${#run_args[@]} -gt 0 ]]; then
            cmd.exe /c start "" "$CARGO_BIN" "${flags[@]}" -- "${run_args[@]}"
        else
            cmd.exe /c start "" "$CARGO_BIN" "${flags[@]}"
        fi
        log "INFO" "Foreground window launched successfully. Terminal released."
    elif [[ ${#run_args[@]} -gt 0 ]]; then
        "$CARGO_BIN" "${flags[@]}" -- "${run_args[@]}" 2>&1 | tee -a "$RUN_LOG"
    else
        "$CARGO_BIN" "${flags[@]}" 2>&1 | tee -a "$RUN_LOG"
    fi
}
#endregion

#region Main
case "$MODE" in
    build)
        build_binary
        ;;
    test)
        run_tests
        ;;
    run)
        launch_viewer
        ;;
esac
#endregion
