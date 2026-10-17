#!/usr/bin/env bash
#region Config
set -e

MODE="full"
DURATION=0
AVD="WebGPU_API34"
CONFIG="release"
HEADLESS=false
RESTART_EMU=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--monitor)  MODE="monitor"; shift ;;
        -e|--emulator) MODE="emulator"; shift ;;
        -b|--build)    MODE="build"; shift ;;
        -d|--deploy)   MODE="deploy"; shift ;;
        -f|--follow)   DURATION=0; shift ;;
        -l|--duration) DURATION="$2"; shift 2 ;;
        -c|--config)   CONFIG="$2"; shift 2 ;;
        --headless)    HEADLESS=true; shift ;;
        -r|--restart-emu) RESTART_EMU=true; shift ;;
        *) echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PACKAGE="org.antigravity.webgpurenderer"
ACTIVITY="android.app.NativeActivity"
LOG_DIR="$SCRIPT_DIR/logs"

SDK="${ANDROID_HOME:-/c/Users/boyce/android_sdk/Sdk}"
ADB="$SDK/platform-tools/adb"
AAPT2="$SDK/build-tools/36.0.0/aapt2"
ZIPALIGN="$SDK/build-tools/36.0.0/zipalign"
APKSIGNER="$SDK/build-tools/36.0.0/lib/apksigner.jar"
EMULATOR="$SDK/emulator/emulator"
JAR="$SDK/platforms/android-36/android.jar"
KEYSTORE="${USERPROFILE:-$HOME}/.android/debug.keystore"
export PATH="${HOME}/.cargo/bin:${USERPROFILE}/.cargo/bin:/c/Users/boyce/.cargo/bin:$PATH"
#endregion

#region Scaffolding
step() {
    echo -e "\n\033[1;96m========================================================\033[0m"
    echo -e "\033[1;92m>>> [$1] [$(basename "$0")] $2\033[0m"
    echo -e "\033[1;96m========================================================\033[0m\n"
}

format_log() {
    local line="$1"
    if [[ "$line" =~ WebGPU-Engine(\([^\)]*\))?:[[:space:]]*(.*) ]]; then
        local msg="${BASH_REMATCH[2]}"
        if [[ "$msg" =~ \[Engine-Metrics\] ]]; then
            echo -e "\033[1;32m[Telemetry] \033[0m\033[1;37m${msg}\033[0m"
        elif [[ "$msg" =~ (Fatal|Error) ]]; then
            echo -e "\033[1;31m[Error]     ${msg}\033[0m"
        elif [[ "$msg" =~ Warn ]]; then
            echo -e "\033[1;33m[Warning]   ${msg}\033[0m"
        else
            echo -e "\033[1;36m[Engine]    \033[0m\033[0;37m${msg}\033[0m"
        fi
    elif [[ "$line" =~ (FATAL\ EXCEPTION|SIGSEGV|SIGABRT|panic|CRASH) ]]; then
        echo -e "\033[1;31m[CRASH]     ${line}\033[0m"
    fi
}

ensure_emulator() {
    step "1/4" "Checking Android Device / Launching Emulator"
    mkdir -p "$LOG_DIR"
    "$ADB" start-server >/dev/null 2>&1 || true
    TARGET_SERIAL=$("$ADB" devices | grep -E '^[a-zA-Z0-9._-]+[[:space:]]+device' | head -n 1 | awk '{print $1}' || true)
    if [ "$RESTART_EMU" = true ] && [ -n "$TARGET_SERIAL" ]; then
        echo "[CI-Emulator] Restart requested. Stopping current device $TARGET_SERIAL..."
        "$ADB" -s "$TARGET_SERIAL" emu kill >/dev/null 2>&1 || true
        sleep 2
        TARGET_SERIAL=""
    fi
    if [ -z "$TARGET_SERIAL" ]; then
        echo "[CI-Emulator] Starting $AVD (logs: logs/emulator_*.log)..."
        local args=("-avd" "$AVD" "-gpu" "host" "-accel" "on" "-feature" "Vulkan" "-no-snapshot-load")
        [ "$HEADLESS" = true ] && args+=("-no-window")
        nohup "$EMULATOR" "${args[@]}" > "$LOG_DIR/emulator_stdout.log" 2> "$LOG_DIR/emulator_stderr.log" & disown
        "$ADB" wait-for-device
        while [ "$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r\n')" != "1" ]; do sleep 1; done
        TARGET_SERIAL=$("$ADB" devices | grep -E '^[a-zA-Z0-9._-]+[[:space:]]+device' | head -n 1 | awk '{print $1}' || true)
    fi
    echo "[CI-Emulator] Target Device: $TARGET_SERIAL"
}

build_and_package() {
    step "2/4" "Compiling Rust & Packaging Signed APK"
    local cargo_args=("build" "--target" "aarch64-linux-android")
    [ "$CONFIG" = "release" ] && cargo_args+=("--release")
    cargo "${cargo_args[@]}"

    local tmp="$SCRIPT_DIR/.tmp"
    local so="$PROJECT_ROOT/target/aarch64-linux-android/$CONFIG/libwebgpu_engine.so"
    local apk="$PROJECT_ROOT/bin/webgpurenderer-0.1.0-arm64-v8a-debug.apk"
    rm -rf "$tmp" && mkdir -p "$tmp" "$(dirname "$apk")"

    "$AAPT2" link -I "$JAR" --manifest "$SCRIPT_DIR/AndroidManifest.xml" -o "$tmp/unsigned.apk"
    python -c "import zipfile, sys; z = zipfile.ZipFile(sys.argv[1], 'a'); z.write(sys.argv[2], sys.argv[3]); z.close()" "$tmp/unsigned.apk" "$so" "lib/arm64-v8a/libwebgpu_engine.so"
    "$ZIPALIGN" -f -p 4 "$tmp/unsigned.apk" "$tmp/aligned.apk"
    java -jar "$APKSIGNER" sign --ks "$KEYSTORE" --ks-pass pass:android --out "$apk" "$tmp/aligned.apk"
    rm -rf "$tmp"
    echo "[CI-Pack] Signed APK: $apk"
}

deploy_app() {
    step "3/4" "Deploying APK and Synchronizing Assets"
    local apk="$PROJECT_ROOT/bin/webgpurenderer-0.1.0-arm64-v8a-debug.apk"
    "$ADB" -s "$TARGET_SERIAL" install -r -d "$apk"

    local gltf="$PROJECT_ROOT/gltf/base_scene_optimized.glb"
    [ -f "$gltf" ] || gltf="$PROJECT_ROOT/gltf/base_scene.glb"
    if [ -f "$gltf" ]; then
        local name; name=$(basename "$gltf")
        local size; size=$(wc -c < "$gltf" | tr -d ' ')
        local remote; remote=$(MSYS_NO_PATHCONV=1 "$ADB" -s "$TARGET_SERIAL" shell "ls -l /sdcard/Android/data/$PACKAGE/files/$name 2>/dev/null" | tr -d '\r')
        if [[ "$remote" != *"$size"* ]]; then
            local win_gltf; win_gltf=$(cygpath -w "$gltf" 2>/dev/null || echo "$gltf")
            MSYS_NO_PATHCONV=1 "$ADB" -s "$TARGET_SERIAL" shell mkdir -p "/sdcard/Android/data/$PACKAGE/files" >/dev/null 2>&1 || true
            MSYS_NO_PATHCONV=1 "$ADB" -s "$TARGET_SERIAL" push "$win_gltf" "/sdcard/Android/data/$PACKAGE/files/$name" >/dev/null
        else
            echo "[CI-Deploy] 3D asset is already synced."
        fi
    fi
}

stream_telemetry() {
    local filter="WebGPU-Engine:* CRASH:* *:F"
    local logcat_path="$LOG_DIR/logcat_latest.log"

    "$ADB" -s "$TARGET_SERIAL" shell settings put system accelerometer_rotation 0 >/dev/null 2>&1 || true
    "$ADB" -s "$TARGET_SERIAL" shell settings put system user_rotation 1 >/dev/null 2>&1 || true
    "$ADB" -s "$TARGET_SERIAL" logcat -c
    "$ADB" -s "$TARGET_SERIAL" shell am start -S -n "$PACKAGE/$ACTIVITY" >/dev/null 2>&1 || true

    # Capture initial screenshot in background after the async scene load settles
    (
        sleep 16
        "$ADB" -s "$TARGET_SERIAL" exec-out screencap -p > "$LOG_DIR/screenshot_latest.png" 2>/dev/null || true
        echo "[CI-Stream] Framebuffer captured: logs/screenshot_latest.png"
    ) &

    if [ "$DURATION" -gt 0 ]; then
        step "4/4" "Streaming Telemetry (${DURATION}s live sample)"
        "$ADB" -s "$TARGET_SERIAL" logcat -v time -s $filter > "$logcat_path" 2>&1 &
        local adb_pid=$!
        local start_ts=$SECONDS
        local last_line=0
        while [ $(( SECONDS - start_ts )) -lt "$DURATION" ]; do
            if [ -f "$logcat_path" ]; then
                local current_lines
                current_lines=$(wc -l < "$logcat_path" | tr -d ' ')
                if [ "$current_lines" -gt "$last_line" ]; then
                    sed -n "$(( last_line + 1 )),${current_lines}p" "$logcat_path" | while IFS= read -r line; do
                        format_log "$line"
                    done
                    last_line="$current_lines"
                fi
            fi
            sleep 0.5
        done
        kill "$adb_pid" 2>/dev/null || true
    else
        step "4/4" "Streaming Continuous Telemetry (heartbeat: 10s, Ctrl+C to stop)"
        "$ADB" -s "$TARGET_SERIAL" logcat -v time -s $filter | tee "$logcat_path" | while IFS= read -r line; do
            format_log "$line"
        done
    fi
}
#endregion

#region Core
echo -e "\033[1;36m[CI-Core] WebGPU Pipeline (${MODE})\033[0m"
ensure_emulator

case "$MODE" in
    emulator) ;;
    monitor)  DURATION=0; stream_telemetry ;;
    build)    build_and_package ;;
    deploy)   deploy_app; stream_telemetry ;;
    full)     build_and_package; deploy_app; stream_telemetry ;;
esac
echo -e "\033[1;32m[CI-Core] Execution complete.\033[0m"
#endregion
