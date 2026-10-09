# Windows Build & Run Pipeline

Pure-Rust WebGPU desktop toolchain for Windows (DirectX 12 / Vulkan backends).

## Directory Overview
- `build.ps1`: Builds native Windows executable (`target/release/webgpu-renderer.exe`).
- `run.ps1`: Launches desktop window with automatic building and backend selection.

## Usage

### 1. Build
```powershell
powershell -ExecutionPolicy Bypass -File .\windows\build.ps1
```

### 2. Run
```powershell
# Launch with default auto-selected backend
powershell -ExecutionPolicy Bypass -File .\windows\run.ps1

# Force DirectX 12
powershell -ExecutionPolicy Bypass -File .\windows\run.ps1 -Backend Dx12

# Force Vulkan
powershell -ExecutionPolicy Bypass -File .\windows\run.ps1 -Backend Vulkan
```
