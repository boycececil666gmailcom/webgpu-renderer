# WebGPU-Renderer

> A modular, real-time 3D rendering engine written in Python — powered by native WebGPU (wgpu-py) and the glTF 2.0 standard.

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![WebGPU](https://img.shields.io/badge/WebGPU-FF5722?style=flat&logo=webgpu&logoColor=white)
![GLFW](https://img.shields.io/badge/GLFW-Window%20Manager-black?style=flat)
![glTF](https://img.shields.io/badge/glTF%202.0-Model%20Format-green?style=flat)
![wgpu-py](https://img.shields.io/badge/wgpu--py-GPU%20Bindings-orange?style=flat)
![License](https://img.shields.io/badge/License-MIT-blue?style=flat)

A lightweight, zero-framework 3D graphics engine that reads industry-standard glTF 2.0 model files and renders them in real time using native WebGPU render pipelines — zero game engine overhead, full pipeline control.

---

## Core Purpose & Business Value

WebGPU-Renderer is a ground-up, dependency-lean 3D renderer that bypasses the abstraction of high-level game engines. It is purpose-built for engineers and researchers who need precise control over every stage of the real-time rendering pipeline.

- **Full Pipeline Visibility**: Every render stage — from glTF buffer parsing to GPU buffer upload, depth sorting, and WGSL shader dispatch — is explicit and inspectable. No black boxes.
- **Industry-Standard 3D Asset Support**: Loads any conformant glTF 2.0 scene file, including meshes, PBR materials, textures, and scene hierarchies, allowing real-world assets to be visualised without conversion.
- **Configurable Without Code Changes**: Camera position, field of view, window dimensions, target frame rate, and directional light can all be tuned via a `.env` file, making the renderer easy to embed in pipelines or demonstrations.
- **Predictable Frame Budget**: A software frame-rate limiter caps rendering to a configurable FPS ceiling, preventing CPU/GPU spin on fast hardware and enabling repeatable performance measurements.
- **Extensible Module Architecture**: The engine is split into focused, single-responsibility modules (`Window`, `Shader`, `Camera`, `Renderer`, `Material`, `GLTFBufferCache`) so any subsystem can be replaced or extended independently.

---

## WebGPU Architecture & Hardware Compilation Stack

WebGPU abstracts cross-platform hardware differences while mapping commands and WGSL shaders directly down to native platform APIs, vendor driver compilers, and physical GPU silicon:

```text
+------------------------------------------------------------------------------------------------+
|             WebGPU End-to-End Pipeline: From Application Code to Hardware Silicon              |
+------------------------------------------------------------------------------------------------+
+------------------+      +------------------+      +------------------+      +------------------+
| 1. App & Shaders |      | 2. IR Translator |      | 3. Platform API  |      | 4. GPU Hardware  |
| Render engine    | ---> | wgpu-core / Naga | ---> | D3D12 / Vulkan   | ---> | Silicon Hardware |
| WGSL Source Code |      | AST Optimization |      | Driver JIT / ICD |      | SM / WGP / Cores |
+------------------+      +------------------+      +------------------+      +------------------+
                                                |
                                                v
+------------------------------------------------------------------------------------------------+
|                      [ Cross-Platform Translation & Compilation Matrix ]                       |
+-----------+--------------------+----------------------+-------------------+--------------------+
| Platform  | Native Backend     | Shader Compilation   | Driver Runtime    | GPU Silicon ISA    |
+-----------+--------------------+----------------------+-------------------+--------------------+
| Windows   | DirectX 12 (D3D12) | WGSL -> HLSL -> DXIL | DXC / WDDM Driver | NVIDIA SASS / RDNA |
| Linux/And | Vulkan API         | WGSL -> SPIR-V Byte  | Vulkan ICD / Mesa | RDNA ISA / NV SASS |
| macOS/iOS | Metal Framework    | WGSL -> MSL -> AIR   | Apple Metal LLVM  | Apple AGX GPU ISA  |
+-----------+--------------------+----------------------+-------------------+--------------------+
                                                |
                                                v
+------------------------------------------------------------------------------------------------+
|                 [ Physical Hardware Execution Layer (GPU Silicon Architecture) ]               |
+------------------------------------------------------------------------------------------------+
| Front-End: Command Processor (CP) reads ring buffers -> Threadgroup Dispatch (Warps/Waves)     |
| Execution: Streaming Multiprocessors (SMs) / Workgroup Processors (WGPs) / Apple GPU Cores     |
| Memory & Scanout: Register Files -> L1/L2 Cache -> VRAM (GDDR6/HBM/UMA) -> Display Engine      |
+------------------------------------------------------------------------------------------------+
```

---

## Repository Structure

```
webgpu-renderer/
├── engine/
│   ├── __init__.py          # Public API: Config, Window, Shader, Camera, Renderer
│   ├── camera.py            # Camera: view + projection matrix generation (pyglm)
│   ├── config.py            # Config: environment-driven settings loader (python-dotenv)
│   ├── gltf_utils.py        # GLTFBufferCache: WebGPU buffer upload + accessor parser
│   ├── material.py          # Material: PBR properties + WebGPU texture lifecycle
│   ├── renderer.py          # Renderer: render loop + frame rate limiter
│   ├── shader.py            # Shader: WGSL module compile + bind group layout
│   └── window.py            # Window: GLFW context + WebGPU surface presentation
├── gltf/
│   ├── mclaren_p1.glb       # glTF 2.0 binary scene asset
│   ├── toyota_supra.gltf    # glTF 2.0 scene descriptor (JSON)
│   ├── toyota_supra_data.bin # Binary vertex/index buffer blob
│   └── toyota_supra_img*.png # 15 PBR texture maps
├── scripts/
│   └── load_supra.sh        # Convenience launcher for the Toyota Supra demo
├── shaders/
│   └── shader.wgsl          # WebGPU WGSL vertex and fragment shader
├── .env                     # Runtime configuration (camera, window, light, FPS)
├── .gitignore
├── main.py                  # Application entry point + render loop orchestration
└── requirements.txt         # Python dependency manifest
```





## License

This project is licensed under the **MIT License**.
