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
|                            Model/asset.blend (Blender 5.0)                      |
|                - Geometry, Transforms, Collections, Materials                   |
|                - Principled BSDF PBR Sockets + Baked Image Textures             |
+---------------------------------------------------------------------------------+
                                       |
                   (Automated glTF 2.0 Export via Python CLI / MCP)
                                       v
+---------------------------------------------------------------------------------+
|                              DECLARATIVE DATA SCHEMA                            |
|                             gltf/base_scene.glb                                 |
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

## 4. Standard Export & Synchronization Procedure

### Step 1: Export glTF from Blender
```bash
"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" -b "Model/asset.blend" --python-expr "
import bpy
bpy.ops.object.select_all(action='DESELECT')
for name in ['Revuelto.Body', 'ENV_Road_Asphalt_ClosedLoop', 'ENV_Terrain_Forest_Floor_Layered', 'ENV_Sky_Column']:
    o = bpy.data.objects.get(name)
    if o: o.select_set(True)
coll = bpy.data.collections.get('Lamborghini_Revuelto')
if coll:
    for o in coll.all_objects: o.select_set(True)
bpy.ops.export_scene.gltf(
    filepath='gltf/base_scene.glb',
    use_selection=True,
    export_format='GLB',
    export_apply=False,
    export_materials='EXPORT',
    export_image_format='AUTO'
)
"
```

### Step 2: Push to Device & Verify
```bash
bash scripts/sync_scene.sh
```

