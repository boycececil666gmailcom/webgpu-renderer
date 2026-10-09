# WebGPU-Renderer (Rust)

A lightweight, high-performance real-time 3D rendering engine written in Rust, powered by the standard `wgpu` graphics crate, `winit`, and the glTF 2.0 specification.

---

## Architectural Highlights

- **Standard Rust WebGPU (`wgpu`)**: Built on idiomatic `wgpu` (WebGPU specification implemented in Rust), mapping directly to DirectX 12 on Windows and Vulkan on Linux and Android.
- **Android-Ready Core Architecture**: The core rendering engine is decoupled in [`src/lib.rs`](file:///c:/Users/boyce/OneDrive/Desktop/webgpu-rust/src/lib.rs) with `crate-type = ["lib", "cdylib"]`, enabling direct desktop execution while remaining immediately portable to Android native activities.
- **Two-Pass Real-Time Rendering**: Separates opaque and blended/masked transparent geometry passes to ensure correct depth sorting.
- **Zero-Framework Asset Pipeline**: Native glTF 2.0 reader supporting `.glb` and `.gltf` scenes, node transform hierarchies, normal matrix generation, and PBR textures.
- **Predictable Frame Budget**: Frame rate limiter capping CPU/GPU usage according to `TARGET_FPS`.

---

## Directory Structure

```
webgpu-rust/
├── Cargo.toml               # Package manifest with lib (cdylib) and bin targets
├── .env                     # Runtime configuration (camera, window, light, FPS)
├── .gitignore               # Ignores build artifacts and target/
├── gltf/
│   └── mclaren_p1.glb       # Default 3D binary model
├── shaders/
│   └── shader.wgsl          # WebGPU WGSL vertex and fragment shader
└── src/
    ├── lib.rs               # Library API exports
    ├── main.rs              # Desktop entrypoint & winit event loop
    ├── config.rs            # .env configuration loader
    ├── camera.rs            # Camera view & perspective projection matrices
    ├── transform.rs         # Transform composition & normal matrix computation
    ├── material.rs          # PBR materials & GPU texture lifecycle
    ├── gltf_loader.rs       # glTF 2.0 / GLB model loader & buffer caching
    └── renderer.rs          # Render pipelines, passes, and uniform buffers
```

---

## Running the Application

### 1. Run with Default Model
```powershell
cargo run --release
```

### 2. Run with Custom glTF/GLB Asset
```powershell
cargo run --release -- path/to/model.glb
```

---

## Compiling for Android (Future Target)

Because the project specifies `crate-type = ["lib", "cdylib"]`, compiling for Android requires only adding the Android target:
```powershell
rustup target add aarch64-linux-android
cargo build --target aarch64-linux-android --release
```
