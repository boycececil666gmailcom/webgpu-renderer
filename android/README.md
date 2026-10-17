# Android Toolchain & CI Pipeline Guide

Pure-Rust WebGPU (`wgpu` + `winit` NativeActivity) Android build, deployment, and live telemetry toolchain.

## Files
- `ci.sh`: Unified Bash script for compilation, packaging, emulator lifecycle, fast in-place deployment, and live ANSI telemetry.
- `AndroidManifest.xml`: Pure NativeActivity manifest (`android:hasCode="false"`, landscape orientation).
- `logs/`: Diagnostic logs (`logcat_latest.log`, `emulator_stdout.log`, `emulator_stderr.log`, `screenshot_latest.png`).

---

## Telemetry Architecture (10s Periodic Heartbeat)

The Rust engine tracks per-frame delta times, lifecycle states, and scene complexity in [`src/telemetry.rs`](file:///c:/Users/boyce/OneDrive/Desktop/webgpu-renderer/src/telemetry.rs). Every 10 seconds, it emits an aggregated heartbeat:
```
[Telemetry] [Engine-Metrics] #1 (Uptime: 00:10) | FPS: 55.2 | FrameTime: 2.66ms (min: 1.79ms, max: 28.64ms) | Meshes: 20 | Instances: 20 | Surface: 2272x1080 | Status: Nominal
[Telemetry] [Engine-Metrics] #2 (Uptime: 00:20) | FPS: 56.1 | FrameTime: 2.60ms (min: 1.65ms, max: 62.85ms) | Meshes: 20 | Instances: 20 | Surface: 2272x1080 | Status: Nominal
```

### Extensibility
`TelemetryTracker` provides modular metric structs (`SceneMetrics`, `RenderMetrics`, etc.) to easily attach future subsystems:
- **Draw Calls & Triangle Counts**: `set_render_stats(draws, tris)`
- **Dynamic Mesh & Instance Counts**: `set_scene_stats(meshes, instances, prims, mats)`
- **Resolution & Surface State**: `set_resolution(width, height)`

---

## Bash Commands (`android/ci.sh`)

### 1. Full Build, Deploy & Continuous Telemetry (Default)
Compiles Rust `cdylib`, packages signed APK, launches emulator (if needed), syncs 3D assets, installs APK, captures initial framebuffer screenshot after 3s, and **streams continuous 10s heartbeats** until Ctrl+C:
```bash
./android/ci.sh
```

### 2. Timed Sample (e.g. for CI / automated tests)
Runs the full pipeline or deployment and exits cleanly after `<sec>` seconds:
```bash
./android/ci.sh -l 30
```

### 3. Live Telemetry Monitor Only (No rebuild/redeploy)
Attaches to the running app and streams the 10s heartbeat:
```bash
./android/ci.sh -m
```

### 4. Fast In-Place Redeploy
Deploys the existing APK and streams continuous telemetry:
```bash
./android/ci.sh -d
```

### 5. Build Only
Compiles Rust `cdylib` and packages signed APK without deploying:
```bash
./android/ci.sh -b
```

### 6. Silent Emulator Launcher
Launches emulator in the background with Vulkan acceleration and isolates hypervisor logs to `logs/emulator_*.log`:
```bash
./android/ci.sh -e
```
