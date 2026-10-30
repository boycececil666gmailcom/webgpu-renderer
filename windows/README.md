# Windows Desktop Preview & CI Pipeline Guide

Desktop development harness for the WebGPU PBR renderer running natively on Windows via `wgpu` (DirectX 12 / Vulkan / Direct3D) and `winit`.

## Files
- `run.sh`: Unified Bash runner for building, testing, and launching the desktop viewer with automatic log rotation.
- `logs/`: Execution and diagnostic logs (`latest.log`, `run_<timestamp>.log`).

---

## Why Platform Folders (`windows/`, `android/`) Instead of `target/`?

A common question is whether platform runners and logs could reside directly in `target/`. In Rust, `target/` is strictly reserved for the compiler:

1. **Destructive Wipes via `cargo clean`**: Cargo treats `target/` as a disposable build scratchpad. Running `cargo clean` recursively deletes the entire `target/` directory without prompt (`rm -rf target/`). Any persistent scripts, configs, documentation, or diagnostic logs placed inside would be destroyed permanently.
2. **Version Control Isolation**: `target/` is globally ignored in `.gitignore`. Scripts located in `target/` cannot be tracked by git, making them invisible to CI/CD systems, collaborators, and new repository clones.
3. **Separation of Concerns**:
   - `windows/` & `android/`: **Human-authored orchestration** (version-controlled, persistent scripts, platform documentation, and log sinks).
   - `target/`: **Machine-generated binaries** (ephemeral object files, incremental compilation caches, and compiled libraries).

---

## Bash Commands (`windows/run.sh`)

### 1. Launch Desktop Preview with Default Scene (Foreground Interactive)
Compiles (if necessary) and launches the desktop viewer in the foreground, rendering the base scene in real-time with live telemetry:
```bash
./windows/run.sh
```

### 2. Spawn Detached Foreground Window
Launches the viewer in a dedicated foreground desktop window while immediately releasing your terminal:
```bash
./windows/run.sh -d
# Or in release:
./windows/run.sh -d --release
```

### 3. Preview a Specific glTF Model
Passes a custom model path to the viewer (validates path existence before opening the window):
```bash
./windows/run.sh -m assets/models/tree_01.glb
# Or directly:
./windows/run.sh assets/models/tree_01.glb
```

### 4. Launch in Release Mode
Runs with full compiler optimizations:
```bash
./windows/run.sh --release -m assets/models/tree_01.glb
```

### 5. Build Desktop Binary Only
Compiles the `webgpu-viewer` binary without launching:
```bash
./windows/run.sh -b
# Or in release:
./windows/run.sh -b --release
```

### 6. Execute Host Test Suite
Runs all 14 unit and integration tests across the engine and desktop binary:
```bash
./windows/run.sh -t
```

---

## Diagnostic Logs
Every execution of `windows/run.sh` tees output both to the console and to a timestamped file in `windows/logs/run_YYYYMMDD_HHMMSS.log`, while automatically updating `windows/logs/latest.log`.
