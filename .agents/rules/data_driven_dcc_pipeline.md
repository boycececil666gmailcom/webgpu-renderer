---
trigger: always_on
description: Project-local directive for data-driven DCC-to-Engine rendering pipeline via Blender and glTF
---

# Data-Driven DCC Pipeline Directive

1. **Blender as Single Source of Truth**:
   - `Model/asset.blend` is the sole source of truth for 3D scene data (geometry, transforms, materials, textures, lighting, and cameras).
   - Any user request to alter visual appearance (colors, paint finishes, roughness, object positions, terrain, foliage, skies, lights) MUST be executed in the active Blender GUI session via Blender MCP (`execute_blender_code`) when available.
   - If Blender MCP is unavailable, the user may explicitly authorize opening Blender manually. In that case, make scene edits in the GUI session and save/export from that session; do not use headless background execution (`blender.exe -b`) for scene authoring because it can desynchronize memory from the open GUI.

2. **Shader Invariance**:
   - Never hardcode scene-specific colors, object-specific thresholds, or temporary visual hacks into WGSL shaders (`shaders/standard_pbr.wgsl`).
   - The engine shaders must remain purely data-driven, evaluating standardized physical PBR parameters (`MaterialUniforms`) delivered by the glTF asset.

3. **Procedural Baking Requirement**:
   - glTF 2.0 cannot serialize procedural Blender node networks (e.g. Voronoi, Noise, Layer Weight).
   - Complex micro-textures (such as metallic flake sparkles or normal maps) must be baked to 2D image textures in Blender before export.

4. **Automated Round-Trip Execution**:
   - Whenever scene edits are made, automatically in the active Blender session via Blender MCP:
     a. Execute scene edits and save `Model/asset.blend` via `bpy.ops.wm.save_mainfile()`.
     b. Export `gltf/base_scene.glb` with selection: car objects, road, terrain, sky column via `bpy.ops.export_scene.gltf(...)`.
     c. Synchronize `base_scene.glb` to the target device via ADB push (`/sdcard/Android/data/org.antigravity.webgpurenderer/files/base_scene.glb`).
     d. Soft-restart `org.antigravity.webgpurenderer/android.app.NativeActivity` and capture a verification frame.

5. **Shader-Aligned Texture Channel Pruning**:
   - Do not link texture map nodes (such as Normal maps or separate Roughness maps) in Blender to Principled BSDF inputs unless the active engine WGSL shaders actively bind and evaluate them.
   - For properties not evaluated as textures by the engine (e.g. metallic, roughness), configure scalar factor sliders directly on the BSDF to avoid serializing unreferenced binary image bloat into `base_scene.glb`.
