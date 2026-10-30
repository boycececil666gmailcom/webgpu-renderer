---
name: foliage_lod_pipeline
description: >-
  Production-grade foliage optimization pipeline in Blender for converting dense 3D vegetation
  (trees, bushes, shrubs) into game-ready LODs (LOD1 leaf cards, LOD2 pruned LODs) using PCA
  oriented bounding quads, silhouette area compensation with leaf enlargement boost, and branch
  spatial island volume pruning.
---

# Foliage & Vegetation LOD Optimization Pipeline

This skill provides an automated, mathematically rigorous workflow to transform high-polygon vegetation models into lightweight, real-time game-ready assets (for WebGPU, Unreal Engine, Unity, Godot) inside Blender.

---

## 1. Problem Statement & Architecture

### Why Standard Decimation Fails on Vegetation
- **Leaf Quad Collapses**: Applying standard Quadric Error Metric (QEM) decimation collapses planar alpha quads into degenerate triangles, ruining UV mapping and stretching alpha textures.
- **Branch Open Boundary Floor**: Foliage branches are typically modeled as hundreds of disconnected, open-ended cylindrical segments with thousands of open boundary edges. QEM collapse halts at open boundary loops, plateauing at bloated polygon counts.

### Solution: 3-Stage Mathematical Pipeline
1. **Principal Component Analysis (PCA) Leaf Cards**: Multi-vertex leaf clusters are segmented into connected components (islands). Covariance matrix eigendecomposition identifies the leaf's primary spine axis ($\mathbf{u}$), width axis ($\mathbf{v}$), and surface normal ($\mathbf{w}$). Each cluster collapses into a single 4-vertex quad card retaining exact atlas UV coordinates.
2. **Silhouette Area Compensation & Size Boost**: When culling $R$ fraction of leaf cards, the remaining cards are scaled around their local centroids by $s = \sqrt{\frac{1}{1 - R}} \times \text{boost}$. This expands the surviving leaves, preventing visual bald spots and thinning at distance while drastically slashing polygon count.
3. **Branch Island Spatial Volume Sorting**: Disconnected branch cylinders are grouped into islands and sorted by 3D bounding box volume ($\Delta x \Delta y \Delta z$). Hidden interior micro-twigs are culled directly, while primary structural trunks are preserved and cleanly decimated with vertex group masks.

---

## 2. Standard LOD Tier Specifications & glTF Architecture

| Level | Geometry Strategy | Material & Shader Setup | glTF 2.0 Compatibility | Typical Poly Count |
| :--- | :--- | :--- | :--- | :--- |
| **LOD -1** | Master High-Poly (Original) | Master shader nodes (`translucency node`, multi-shader chains) | Offline / Cycles only (Incompatible with glTF) | 12k – 270k+ |
| **LOD 0** | **Identical to LOD -1** (No geometry changes) | **Baked PBR**: Consolidated RGBA BaseColor (albedo + translucency + alpha mask), Direct `Principled BSDF` | **100% glTF Compliant** (`alphaMode: MASK`, `doubleSided: true`) | 12k – 270k+ |
| **LOD 1** | PCA Leaf Cards + **1.35x** size boost | Shares LOD 0 Baked PBR material | **100% glTF Compliant** | 1,100 – 25,000 |
| **LOD 2** | Pruned Cards + **1.85x** size boost | Shares LOD 0 Baked PBR material | **100% glTF Compliant** | 330 – 6,400 |
| **LOD 3** | **Tri-Star Billboard** (3 intersecting quads at $0^\circ, 60^\circ, 120^\circ$ with tight alpha crop) | Rendered orthographic impostor RGBA, alpha mask, radial normals | **100% glTF Compliant** | **3 quads (6 tris, 12 verts)** |

### Eliminating Billboard "Thinness" via Foreground UV Auto-Cropping & Tri-Star Planes
Standard crossing quads frequently appear flat, squished, or paper-thin from oblique camera angles due to two issues:
1. **Empty Alpha Canvas Padding**: When an orthographic render occupies only 45-60% of a square $1024 \times 1024$ canvas, mapping the entire $[0, 1]$ UV space compresses the foliage mesh horizontally by half.
   - **Fix**: The pipeline analyzes the rendered alpha channel (`pix[:, :, 3] > 0.05`) to compute the tight active bounding box $(u_0, u_1, v_0, v_1)$. The quad width is assigned to the physical foliage width, and quad UVs map strictly to the active foliage bounds, restoring 100% physical silhouette presence.
2. **2-Plane Cruciform Blind Angles**: An orthogonal 2-plane cross ($90^\circ$) has extreme edge-on blind spots at $45^\circ$ angles.
   - **Fix**: Upgraded to a **3-plane Tri-Star arrangement** ($0^\circ, 60^\circ, 120^\circ$) with radial vertex normals pointing outward from the mesh center line. This ensures full 360-degree volumetric thickness, omnidirectional light scattering, and zero paper-thin edge artifacts.

### Shared Overlapping UV Handling & Single-Material Atlas Architecture
Foliage leaf quads share normalized `[0, 1]` UV coordinates on a leaf atlas. Running Blender's built-in `Smart UV Project` destroys this shared atlas by scattering thousands of microscopic UV islands. Instead, textures are consolidated using a **Column-Strip 2D Texture Atlas**:

1. **Atlas Division**: A 2K texture ($2048 \times 2048$) is partitioned into vertical column strips:
   - **Column 0 ($U \in [0.0, 0.50]$)**: High-resolution Leaf RGBA (albedo + translucency + alpha cutout mask).
   - **Column 1 ($U \in [0.50, 0.75]$)**: Primary Branch bark (seamless vertical tile $V \in [0, 1]$).
   - **Column 2 ($U \in [0.75, 1.00]$)**: Secondary Branch bark (seamless vertical tile $V \in [0, 1]$).
2. **UV Column Remapping**:
   - Leaves: $U' = U \times 0.50, V' = V$.
   - Branch 02: $U' = 0.50 + U \times 0.25, V' = V$.
   - Branch 03: $U' = 0.75 + U \times 0.25, V' = V$.
   Because $V$ coordinate wraps seamlessly with standard hardware repeat (`wrapT = REPEAT`), the bark continues tiling vertically without distortion, while $U$ stays strictly bounded within each column without cross-bleeding.
3. **Single Draw Call**: All mesh polygon material indices collapse to `0`, reducing the model from 3-4 material slots to **exactly 1 material slot** (`1 Draw Call` in WebGPU).

---

## 3. Python Execution Runbook

The pipeline script is located in `./scripts/optimize_foliage_lod.py`.

### A. Execution Inside Blender (Interactive / MCP)

```python
#region RunPipelineInBlender
import bpy
import sys
from pathlib import Path

# Import the reusable skill script
skill_path = Path(bpy.data.filepath).parent / ".agents" / "skills" / "foliage_lod_pipeline" / "scripts"
if str(skill_path) not in sys.path:
    sys.path.append(str(skill_path))

from optimize_foliage_lod import generate_foliage_lod

# Example: Process Bush 02
src_obj = bpy.data.objects["AE_15TH_FOREST_BUSH_02_LOD0"]

# Generate LOD1 (Mid-level bridge: 1,200 leaf cards + 1.35x boost)
mesh_lod1 = generate_foliage_lod(
    src_obj=src_obj,
    leaf_mat_idx=0,
    cull_redundant_petiole=False,
    branch_island_ratio=0.25,
    branch_decimate_ratio=0.35,
    target_leaf_count=1200,
    leaf_size_boost=1.35,
    name_suffix="LOD1"
)

# Generate LOD2 (Game-ready cutoff: 450 leaf cards + 1.85x boost)
mesh_lod2 = generate_foliage_lod(
    src_obj=src_obj,
    leaf_mat_idx=0,
    cull_redundant_petiole=False,
    branch_island_ratio=0.06,
    branch_decimate_ratio=0.15,
    target_leaf_count=450,
    leaf_size_boost=1.85,
    name_suffix="LOD2"
)
#endregion
```

### B. Headless CLI Execution (Batch Automation)

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" -b "project.blend" --python ".agents/skills/foliage_lod_pipeline/scripts/optimize_foliage_lod.py"
```

---

## 4. Parameter Tuning Guidelines

1. **Leaf Size Boost (`leaf_size_boost`)**:
   - `1.30` – `1.40`: Subtle enlargement, ideal for LOD1 where card density is still moderate (~1,200 to 2,500 cards).
   - `1.85` – `2.35`: Pronounced enlargement, ideal for LOD2 where card counts drop below 500 to keep the silhouette fully opaque.
2. **Branch Island Ratio (`branch_island_ratio`)**:
   - `0.12` – `0.25`: Retains major branch forks and structural limbs while stripping micro-twigs.
   - `0.02` – `0.06`: Strips everything except the core root trunk and main primary forks.
3. **Cull Redundant Petiole (`cull_redundant_petiole`)**:
   - Set to `True` for assets where leaf stems are modeled as a separate material slot (e.g., `Forest_Bush_Petiole_01`).
   - Set to `False` for models where leaves connect directly to branches or share material indices.
