---
name: data_driven_dcc_pipeline
description: Project-local automated DCC-to-Engine rendering pipeline connecting Blender, glTF 2.0 PBR, and WebGPU.
---

# Data-Driven DCC-to-Engine Pipeline

This skill defines the contract and execution protocols for synchronizing 3D scene changes from Blender (`asset.blend`) to the WebGPU runtime engine via glTF 2.0.

---

## 1. Architectural Contract

```
+---------------------------------------------------------------------------------+
|                               SINGLE SOURCE OF TRUTH                            |
|                            dcc/asset.blend (Blender 5.0)                        |
|                - Geometry, Transforms, Collections, Materials                   |
|                - Principled BSDF PBR Sockets + Baked Image Textures             |
+---------------------------------------------------------------------------------+
                                       |
                   (Automated glTF 2.0 Export via Blender MCP)
                                       v
+---------------------------------------------------------------------------------+
|                              DECLARATIVE DATA SCHEMA                            |
|                             assets/models/base_scene.glb                        |
|                - Core PBR (baseColor, metallic, roughness, normal)              |
|                - Extensions (KHR_materials_unlit, KHR_materials_clearcoat)      |
+---------------------------------------------------------------------------------+
                                       |
                   (Asset Transfer via ADB Push / Hot-Sync)
                                       v
+---------------------------------------------------------------------------------+
|                             DATA-DRIVEN GPU RUNTIME                             |
|                   Rust gltf_loader.rs + shaders/standard_pbr.wgsl               |
|                - Evaluates MaterialUniforms strictly without hardcoding         |
|                - Renders on Android NativeActivity / Desktop WebGPU             |
+---------------------------------------------------------------------------------+
```

---

## 2. Material Mapping Reference

| Blender Principled BSDF Socket | glTF 2.0 Property / Extension | Engine `MaterialUniforms` | WGSL Treatment in `standard_pbr.wgsl` |
| :--- | :--- | :--- | :--- |
| **Base Color** | `pbrMetallicRoughness.baseColorFactor` | `base_color: [f32; 4]` | Multiplies texture albedo (`base_color * tex`) |
| **Metallic** | `pbrMetallicRoughness.metallicFactor` | `metallic: f32` | Energy conservation `kD = (1 - F) * (1 - metallic)` |
| **Roughness** | `pbrMetallicRoughness.roughnessFactor` | `roughness: f32` | Specular Blinn-Phong/GGX lobe width |
| **Coat Weight** | `KHR_materials_clearcoat.clearcoatFactor` | `clearcoat: f32` | Top polyurethane lacquer reflection layer |
| **Alpha Mode** | `material.alphaMode` (`OPAQUE`/`MASK`/`BLEND`) | `alpha_mode: u32` | `0`: Opaque, `1`: Alpha test cutoff, `2`: Transparent |
| **Alpha Cutoff** | `material.alphaCutoff` | `alpha_cutoff: f32` | Discards fragments below cutoff threshold |
| **Unlit Surface** | `KHR_materials_unlit` | `is_unlit: u32` | Bypasses lighting; outputs raw unlit color |

---

## 3. Procedural Baking Mandate

- **Strict Constraint**: glTF 2.0 **cannot** serialize procedural math nodes (`Voronoi`, `Noise`, `ColorRamp`, `LayerWeight`, `Math`).
- **Resolution**: Any procedural detailing (e.g., metallic flake specks, carbon weave noise, road cracks) must be baked into an image texture (PNG/WebP) and connected via `ShaderNodeTexImage` to the respective BSDF socket prior to GLB export.

---

## 4. Shader-Aligned Texture Channel Pruning

- **Core Principle**: Only connect texture channels in Blender that the active engine WGSL shaders bind and sample.
- **Current Engine Shader (`standard_pbr.wgsl`) Scope**:
  - Bound texture: `@group(2) @binding(1) mat_texture: texture_2d<f32>` (Albedo / Base Color only).
  - Material properties (`metallic`, `roughness`, `clearcoat`): Evaluated strictly as scalar uniforms from `MaterialUniforms`.
- **Constraint**: Do not plug separate Normal Map or Roughness Map textures into the Principled BSDF unless the WGSL shader pipeline has been upgraded to bind them. Linking unused 4K Normal/Roughness maps adds ~115 MB of dead buffer bloat that the glTF loader ignores at runtime.
- **Material Setup**: Configure `Roughness` and `Metallic` as scalar slider values directly on the Principled BSDF node.

---

## 5. Standard Export & Synchronization Procedure

### Step 1: Export glTF from Blender via Blender MCP (`execute_blender_code`)
```python
import bpy

bpy.ops.object.select_all(action='DESELECT')
for name in ['Revuelto.Body', 'ENV_Road_Asphalt_ClosedLoop', 'ENV_Terrain_Forest_Floor_Layered', 'ENV_Sky_Column']:
    o = bpy.data.objects.get(name)
    if o:
        o.select_set(True)

coll = bpy.data.collections.get('Lamborghini_Revuelto')
if coll:
    for o in coll.all_objects:
        o.select_set(True)

bpy.ops.wm.save_mainfile()
bpy.ops.export_scene.gltf(
    filepath='assets/models/base_scene.glb',
    use_selection=True,
    export_format='GLB',
    export_apply=False,
    export_materials='EXPORT',
    export_image_format='AUTO'
)
```

### Step 2: Push to Device & Verify
```bash
bash scripts/sync_scene.sh
```

