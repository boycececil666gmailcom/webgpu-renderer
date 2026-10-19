#!/usr/bin/env python3
#region Imports
import math
import os
import sys
from mathutils import Vector, Euler
import bpy
#endregion

#region Types
# Modular glTF Export Script
#endregion

#region Scaffolding
def log_step(msg: str) -> None:
    print(f"[EXPORT-MODULAR] {msg}")
#endregion

#region Core
def export_modular_assets() -> None:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    gltf_dir = os.path.join(project_root, "gltf")
    os.makedirs(gltf_dir, exist_ok=True)

    base_scene_glb = os.path.join(gltf_dir, "base_scene.glb")
    leaves_glb = os.path.join(gltf_dir, "leaves.glb")

    # 1. Export standalone leaves prototype
    log_step("Exporting standalone leaves prototype: gltf/leaves.glb...")
    bpy.ops.object.select_all(action='DESELECT')
    leaf_obj = bpy.data.objects.get("ENV_Foliage_Leaves_Scatter")
    if leaf_obj:
        leaf_obj.select_set(True)
        bpy.ops.export_scene.gltf(
            filepath=leaves_glb,
            use_selection=True,
            export_format='GLB',
            export_apply=False,
            export_materials='EXPORT',
            export_image_format='AUTO',
            export_cameras=False,
            export_lights=False,
        )
        log_step(f"Exported leaves prototype: {leaves_glb}")
    else:
        raise ValueError("ENV_Foliage_Leaves_Scatter object not found in asset.blend")

    # 2. Preserve vehicle hierarchy and transforms from Blender
    log_step("Verifying vehicle hierarchy from Blender...")
    car_coll = bpy.data.collections.get("Lamborghini_Revuelto")
    car_root = bpy.data.objects.get("Revuelto.Body")
    if not car_root:
        car_root = bpy.data.objects.new("Revuelto.Body", None)
        car_root.empty_display_type = 'ARROWS'
        car_root.empty_display_size = 2.0
        car_coll.objects.link(car_root)

    for o in car_coll.objects:
        if o != car_root and o.parent != car_root:
            o.parent = car_root

    bpy.context.view_layer.update()
    log_step(f"Car hierarchy verified at Blender world transform: {car_root.location}")

    # 3. Export main scene (excluding leaf prototype)
    log_step("Exporting main scene: gltf/base_scene.glb...")
    bpy.ops.object.select_all(action='DESELECT')
    car_root.select_set(True)
    for o in car_coll.all_objects:
        o.select_set(True)

    for name in [
        "ENV_Road_Asphalt_ClosedLoop",
        "ENV_Terrain_Forest_Floor_Layered",
        "ENV_Sky_Column",
        "CAM_Scene_Follow",
        "Sun"
    ]:
        o = bpy.data.objects.get(name)
        if o:
            o.select_set(True)

    bpy.ops.export_scene.gltf(
        filepath=base_scene_glb,
        use_selection=True,
        export_format='GLB',
        export_apply=False,
        export_materials='EXPORT',
        export_image_format='AUTO',
        export_cameras=True,
        export_lights=True,
    )
    log_step(f"Exported main scene: {base_scene_glb}")
#endregion

#region Main
if __name__ == "__main__":
    export_modular_assets()
    sys.exit(0)
#endregion

