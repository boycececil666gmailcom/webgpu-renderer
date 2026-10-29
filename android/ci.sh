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
[ -f "${ADB}.exe" ] && ADB="${ADB}.exe"
AAPT2="$SDK/build-tools/36.0.0/aapt2"
[ -f "${AAPT2}.exe" ] && AAPT2="${AAPT2}.exe"
ZIPALIGN="$SDK/build-tools/36.0.0/zipalign"
[ -f "${ZIPALIGN}.exe" ] && ZIPALIGN="${ZIPALIGN}.exe"
APKSIGNER="$SDK/build-tools/36.0.0/lib/apksigner.jar"
EMULATOR="$SDK/emulator/emulator"
[ -f "${EMULATOR}.exe" ] && EMULATOR="${EMULATOR}.exe"
JAR="$SDK/platforms/android-36/android.jar"
KEYSTORE="${USERPROFILE:-$HOME}/.android/debug.keystore"
LLVM_MINGW_BIN="/c/Users/boyce/AppData/Local/Microsoft/WinGet/Packages/MartinStorsjo.LLVM-MinGW.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe/llvm-mingw-20260908-ucrt-x86_64/bin"
export PATH="${LLVM_MINGW_BIN}:${HOME}/.cargo/bin:${USERPROFILE}/.cargo/bin:/c/Users/boyce/.cargo/bin:$PATH"
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
    TARGET_SERIAL=$("$ADB" devices | awk '$1 ~ /^emulator-/ && $2 == "device" { print $1; exit }')
    if [ "$RESTART_EMU" = true ] && [ -n "$TARGET_SERIAL" ]; then
        echo "[CI-Emulator] Restart requested. Stopping current device $TARGET_SERIAL..."
        "$ADB" -s "$TARGET_SERIAL" emu kill >/dev/null 2>&1 || true
        sleep 2
        TARGET_SERIAL=""
    fi
    if [ -z "$TARGET_SERIAL" ]; then
        echo "[CI-Emulator] Starting $AVD (logs: logs/emulator_*.log)..."
        local avd_home="${ANDROID_AVD_HOME:-${ANDROID_USER_HOME:-$HOME/.android}/avd}"
        local avd_dir="$avd_home/$AVD.avd"
        local avd_config="$avd_dir/config.ini"
        local user_ini="$avd_dir/emulator-user.ini"
        if [ -f "$avd_config" ]; then
            if grep -q '^hw\.initialOrientation=' "$avd_config"; then
                sed -i 's/^hw\.initialOrientation=.*/hw.initialOrientation=landscape/' "$avd_config"
            else
                printf '\nhw.initialOrientation=landscape\n' >> "$avd_config"
            fi
        fi
        if [ -f "$user_ini" ]; then
            sed -i \
                -e 's/^window\.x = .*/window.x = 0/' \
                -e 's/^window\.y = .*/window.y = 0/' \
                "$user_ini"
        fi
        local args=("-avd" "$AVD" "-gpu" "host" "-accel" "on" "-feature" "Vulkan" "-no-snapshot-load")
        [ "$HEADLESS" = true ] && args+=("-no-window")
        nohup "$EMULATOR" "${args[@]}" > "$LOG_DIR/emulator_stdout.log" 2> "$LOG_DIR/emulator_stderr.log" & disown
        local attempts=0
        while [ -z "$TARGET_SERIAL" ] && [ "$attempts" -lt 180 ]; do
            TARGET_SERIAL=$("$ADB" devices | awk '$1 ~ /^emulator-/ && $2 == "device" { print $1; exit }')
            [ -n "$TARGET_SERIAL" ] || { sleep 1; attempts=$((attempts + 1)); }
        done
        if [ -z "$TARGET_SERIAL" ]; then
            echo "[CI-Emulator] No ready emulator appeared in ADB within 180 seconds." >&2
            echo "[CI-Emulator] Connected devices:" >&2
            "$ADB" devices -l >&2 || true
            echo "[CI-Emulator] See $LOG_DIR/emulator_stdout.log and emulator_stderr.log." >&2
            return 1
        fi
        "$ADB" -s "$TARGET_SERIAL" wait-for-device
        while [ "$("$ADB" -s "$TARGET_SERIAL" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r\n')" != "1" ]; do sleep 1; done
    fi
    if [ -z "$TARGET_SERIAL" ]; then
        echo "[CI-Emulator] No ready emulator found in ADB." >&2
        echo "[CI-Emulator] Connected devices:" >&2
        "$ADB" devices -l >&2 || true
        return 1
    fi
    "$ADB" -s "$TARGET_SERIAL" shell settings put system accelerometer_rotation 0 >/dev/null 2>&1 || true
    "$ADB" -s "$TARGET_SERIAL" shell settings put system user_rotation 1 >/dev/null 2>&1 || true
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

    sync_file() {
        local src="$1"
        if [ -f "$src" ]; then
            local name; name=$(basename "$src")
            local size; size=$(wc -c < "$src" | tr -d ' ')
            local remote; remote=$(MSYS_NO_PATHCONV=1 "$ADB" -s "$TARGET_SERIAL" shell "wc -c </sdcard/Android/data/$PACKAGE/files/$name 2>/dev/null" | tr -d '\r ')
            local local_hash; local_hash=$(sha256sum "$src" | awk '{print $1}')
            local remote_hash; remote_hash=$(MSYS_NO_PATHCONV=1 "$ADB" -s "$TARGET_SERIAL" shell "toybox sha256sum /sdcard/Android/data/$PACKAGE/files/$name 2>/dev/null" | awk '{print $1}' | tr -d '\r')
            if [[ "$remote" != "$size" || "$remote_hash" != "$local_hash" ]]; then
                local win_src; win_src=$(cygpath -w "$src" 2>/dev/null || echo "$src")
                MSYS_NO_PATHCONV=1 "$ADB" -s "$TARGET_SERIAL" shell mkdir -p "/sdcard/Android/data/$PACKAGE/files" >/dev/null 2>&1 || true
                MSYS_NO_PATHCONV=1 "$ADB" -s "$TARGET_SERIAL" push "$win_src" "/sdcard/Android/data/$PACKAGE/files/$name" >/dev/null
                echo "[CI-Deploy] Synced $name to device."
            else
                echo "[CI-Deploy] $name is already synced."
            fi
        fi
    }

    for glb in "$PROJECT_ROOT"/gltf/*.glb; do
        [ -f "$glb" ] && sync_file "$glb"
    done
    sync_file "$PROJECT_ROOT/config/scatter.json"
    sync_file "$PROJECT_ROOT/Model/textures/autumn_forest_01_1k.png"
}

stream_telemetry() {
    local filter="WebGPU-Engine:* CRASH:* *:F"
    local logcat_path="$LOG_DIR/logcat_latest.log"

    "$ADB" -s "$TARGET_SERIAL" shell settings put system accelerometer_rotation 0 >/dev/null 2>&1 || true
    "$ADB" -s "$TARGET_SERIAL" shell settings put system user_rotation 1 >/dev/null 2>&1 || true
    "$ADB" -s "$TARGET_SERIAL" logcat -c
    "$ADB" -s "$TARGET_SERIAL" shell am start -S -n "$PACKAGE/$ACTIVITY" >/dev/null 2>&1 || true

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

        # Synchronously capture settled verification frame
        local win_dest
        win_dest=$(cygpath -w "$LOG_DIR/screenshot_latest.png" 2>/dev/null || echo "$LOG_DIR/screenshot_latest.png")
        MSYS_NO_PATHCONV=1 "$ADB" -s "$TARGET_SERIAL" shell screencap -p /data/local/tmp/screenshot_render.png
        MSYS_NO_PATHCONV=1 "$ADB" -s "$TARGET_SERIAL" pull /data/local/tmp/screenshot_render.png "$win_dest"
        echo "[CI-Stream] Framebuffer captured: logs/screenshot_latest.png"
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
case "$MODE" in
    emulator) ensure_emulator ;;
    monitor)  ensure_emulator; DURATION=0; stream_telemetry ;;
    build)    build_and_package ;;
    deploy)   ensure_emulator; deploy_app; stream_telemetry ;;
    full)     ensure_emulator; build_and_package; deploy_app; stream_telemetry ;;
esac
echo -e "\033[1;32m[CI-Core] Execution complete.\033[0m"
#endregion
