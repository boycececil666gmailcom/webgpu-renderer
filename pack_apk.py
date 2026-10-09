#!/usr/bin/env python3
# region Packaging
import io
import os
import shutil
import subprocess
import time
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(SCRIPT_DIR, "bin")
SRC_APK = os.path.join(BIN_DIR, "webgpurenderer-0.1.0-arm64-v8a-debug.apk")
SO_PATH = os.path.join(SCRIPT_DIR, "target", "aarch64-linux-android", "release", "libwebgpu_engine.so")
TMP_DIR = os.path.join(SCRIPT_DIR, "build_apk_tmp")

print("[Pack-Android] Starting Android APK packaging pipeline...")

if not os.path.exists(SRC_APK):
    print(f"[Pack-Android] Error: Base APK not found at {SRC_APK}")
    sys.exit(1)

if os.path.exists(TMP_DIR):
    shutil.rmtree(TMP_DIR)
os.makedirs(TMP_DIR)

# 1. Read files to bundle
assets_to_bundle = {}
for asset_rel in ["shaders/shader.wgsl", ".env"]:
    full_path = os.path.join(SCRIPT_DIR, asset_rel)
    if os.path.exists(full_path):
        with open(full_path, "rb") as f:
            assets_to_bundle[f"assets/{asset_rel}"] = f.read()

# 2. Build unsigned APK
unsigned_apk = os.path.join(TMP_DIR, "unsigned.apk")
with zipfile.ZipFile(SRC_APK, "r") as zin, zipfile.ZipFile(unsigned_apk, "w", compression=zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if item.filename.startswith("META-INF/"):
            continue
        if item.filename in assets_to_bundle:
            continue
        zout.writestr(item, zin.read(item.filename))

    for target_path, data in assets_to_bundle.items():
        zout.writestr(target_path, data)

    if os.path.exists(SO_PATH):
        print(f"[Pack-Android] Injecting compiled Rust cdylib: {SO_PATH}")
        with open(SO_PATH, "rb") as f:
            so_bytes = f.read()
        zout.writestr("lib/arm64-v8a/libwebgpu_engine.so", so_bytes)

# 3. Zipalign
aligned_apk = os.path.join(TMP_DIR, "aligned.apk")
try:
    subprocess.run(["zipalign", "-f", "-p", "4", unsigned_apk, aligned_apk], check=True)
except Exception:
    # Fallback to invoking via WSL if running in native Windows without zipalign in PATH
    wsl_unsigned = unsigned_apk.replace("\\", "/").replace("C:", "/mnt/c")
    wsl_aligned = aligned_apk.replace("\\", "/").replace("C:", "/mnt/c")
    subprocess.run(["wsl", "-d", "Ubuntu-22.04", "--", "zipalign", "-f", "-p", "4", wsl_unsigned, wsl_aligned], check=True)

# 4. Sign with debug.keystore
final_apk = os.path.join(TMP_DIR, "final.apk")
keystore = os.path.expanduser("~/.android/debug.keystore")
try:
    subprocess.run([
        "apksigner", "sign",
        "--ks", keystore,
        "--ks-pass", "pass:android",
        "--key-pass", "pass:android",
        "--ks-key-alias", "androiddebugkey",
        "--out", final_apk,
        aligned_apk
    ], check=True)
except Exception:
    wsl_aligned = aligned_apk.replace("\\", "/").replace("C:", "/mnt/c")
    wsl_final = final_apk.replace("\\", "/").replace("C:", "/mnt/c")
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "apksigner", "sign",
        "--ks", "/home/boyce/.android/debug.keystore",
        "--ks-pass", "pass:android",
        "--key-pass", "pass:android",
        "--ks-key-alias", "androiddebugkey",
        "--out", wsl_final,
        wsl_aligned
    ], check=True)

shutil.copyfile(final_apk, SRC_APK)
print(f"[Pack-Android] SUCCESS: Packaged and signed APK ready at {SRC_APK}")
# endregion
