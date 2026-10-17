# WebGPU-Renderer (Android NativeActivity)

A lightweight, high-performance real-time 3D rendering engine written in Rust targeting Android (`aarch64-linux-android`), powered by the standard `wgpu` graphics crate (Vulkan backend), `winit` NativeActivity, and the glTF 2.0 specification.

---

## Architectural Highlights

- **Pure Rust NativeActivity**: Completely free of Java/Kotlin wrapper layers (`android:hasCode="false"`), executing directly inside `android.app.NativeActivity` via `libwebgpu_engine.so`.
- **Direct Vulkan Backend**: Utilizes `wgpu` mapping directly to high-performance Vulkan drivers on mobile devices and hardware-accelerated Android emulators.
- **Two-Pass Real-Time Rendering**: Separates opaque and blended/masked transparent geometry passes to ensure correct depth sorting.
- **Zero-Framework Asset Pipeline**: Native glTF 2.0 reader supporting `.glb` and `.gltf` scenes, node transform hierarchies, normal matrix generation, and PBR textures.
- **Mobile Lifecycle Aware**: Reacts to Android lifecycle events (`Event::Resumed`, `Event::Suspended`), properly configuring the hardware surface and dropping GPU resources when backgrounded.

---

## Directory Structure

```
webgpu-renderer/
├── Cargo.toml               # Package manifest configuring cdylib for Android
├── .gitignore               # Ignores build artifacts and target/
├── android/                 # Android NativeActivity packaging & deployment
│   ├── AndroidManifest.xml  # NativeActivity manifest configuration
│   ├── build.ps1            # Compiles Rust cdylib and outputs aligned APK
│   ├── pack.ps1             # Assembles .so, assets, and signs debug APK
│   ├── deploy.ps1           # Installs APK on device/emulator & streams logcat
│   ├── ci.ps1               # Automated end-to-end emulator CI pipeline
│   ├── setup_emulator.ps1   # Provisions hardware-accelerated AVD
│   └── run_emulator.ps1     # Boots Android emulator with Vulkan passthrough
├── gltf/
│   ├── base_scene.glb          # Default 3D scene (Lamborghini, closed road, layered terrain)
│   ├── foliage_prototypes.glb  # Foliage prototype assets for GPU instancing
│   └── foliage_manifest.json   # Foliage LOD metadata & scatter parameters
├── shaders/
│   └── shader.wgsl          # WebGPU WGSL vertex and fragment shader
└── src/
    ├── lib.rs               # Library entry point (android_main & lifecycle)
    ├── config.rs            # Camera, lighting, and target frame rate config
    ├── material.rs          # PBR materials & GPU texture lifecycle
    ├── gltf_loader.rs       # glTF 2.0 / GLB model loader & buffer caching
    └── renderer.rs          # Render pipelines, passes, and uniform buffers
```

---

## Build & Run Pipeline

### 1. Compile & Package APK
```powershell
powershell -ExecutionPolicy Bypass -File .\android\build.ps1 -Configuration release
```

### 2. Deploy & Stream Logcat
```powershell
# Auto-detects connected device or running emulator
powershell -ExecutionPolicy Bypass -File .\android\deploy.ps1
```

### 3. Run Automated CI in Emulator
```powershell
powershell -ExecutionPolicy Bypass -File .\android\ci.ps1 -Headless
```
