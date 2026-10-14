# Android Build & Debug Guide

Pure-Rust WebGPU (`wgpu` + `winit` NativeActivity) Android build and deployment toolchain.

- `ci.ps1`: All-in-one consolidated CI script: builds APK natively, auto-creates/spins up Vulkan Android emulator, syncs 3D assets, installs APK, and streams logs into a dedicated subfolder (`android/logs/`).
- `AndroidManifest.xml`: Pure-NativeActivity manifest without Java/Kotlin code (`android:hasCode="false"`).
- `build.ps1`: One-step script to compile Rust `cdylib` via Cargo and produce signed APK.
- `pack.ps1`: Packages compiled `.so`, WGSL shaders, and glTF assets into an aligned, debug-signed APK.
- `setup_emulator.ps1`: Automated installation of Android Emulator, API 34 system image, and AVD with Vulkan host GPU passthrough.
- `run_emulator.ps1`: Launches the AVD with host acceleration and waits for boot completion.
- `deploy.ps1`: Connects to physical device or running emulator, installs APK, and streams logcat.

## Consolidated CI Workflow (All-in-One)

Run the full end-to-end pipeline in a single command:
```powershell
# Runs complete CI: native packaging, auto emulator spin-up, asset sync, and log output
powershell -ExecutionPolicy Bypass -File .\android\ci.ps1

# Options:
# -SkipRustBuild         : Skip cargo compilation, package and deploy existing .so
# -LogDurationSeconds 30 : Monitor app output for 30s before clean exit (default 15s)
# -LogDurationSeconds 0  : Stream continuously until Ctrl+C
# -Headless              : Run emulator without window (-no-window)
# -Subfolder "logs"      : Target folder for session transcripts and logcats
```

## Modular Commands

### 1. Build Android APK
```powershell
powershell -ExecutionPolicy Bypass -File .\android\build.ps1
```

### 2. Deploy to Emulator or Physical Device
```powershell
# Auto-detects running emulator or connected device
powershell -ExecutionPolicy Bypass -File .\android\deploy.ps1

# Or target specific physical device IP
powershell -ExecutionPolicy Bypass -File .\android\deploy.ps1 -DeviceIp "10.36.154.26"
```
