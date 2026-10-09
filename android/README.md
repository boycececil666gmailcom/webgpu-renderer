# Android Build & Debug Guide

Pure-Rust WebGPU (`wgpu` + `winit` NativeActivity) Android build and deployment toolchain.

## Directory Overview
- `AndroidManifest.xml`: Pure-NativeActivity manifest without Java/Kotlin code (`android:hasCode="false"`).
- `build.ps1`: One-step script to compile Rust `cdylib` via Cargo and produce signed APK.
- `pack.ps1`: Packages compiled `.so`, WGSL shaders, and glTF assets into an aligned, debug-signed APK.
- `deploy.ps1`: Connects to physical device over wireless ADB, installs APK, and streams logcat.

## Usage

### 1. Build Android APK
```powershell
powershell -ExecutionPolicy Bypass -File .\android\build.ps1
```

### 2. Deploy to Physical Device (Wireless ADB)
```powershell
powershell -ExecutionPolicy Bypass -File .\android\deploy.ps1 -DeviceIp "10.36.154.26"
```
