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
    models_dir = os.path.join(project_root, "assets", "models")
    os.makedirs(models_dir, exist_ok=True)

    base_scene_glb = os.path.join(models_dir, "base_scene.glb")
    leaves_glb = os.path.join(models_dir, "leaves.glb")

    # 1. Export standalone leaves prototypes (LOD 0, LOD 1, LOD 2)
    log_step("Exporting standalone leaves prototypes (LOD 0, 1, 2)...")
    leaf_obj = bpy.data.objects.get("ENV_Foliage_Leaves_Scatter")
    if not leaf_obj:
        raise ValueError("ENV_Foliage_Leaves_Scatter object not found in asset.blend")

    def export_single_mesh(obj, out_path):
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.gltf(
            filepath=out_path,
            use_selection=True,
            export_format='GLB',
            export_apply=True,
            export_materials='EXPORT',
            export_image_format='AUTO',
            export_cameras=False,
            export_lights=False,
        )
        log_step(f"Exported: {out_path} ({os.path.getsize(out_path)} bytes)")

    lod0_path = os.path.join(models_dir, "leaves_lod0.glb")
    export_single_mesh(leaf_obj, lod0_path)
    export_single_mesh(leaf_obj, leaves_glb)

    # LOD 1 (0.25 decimation)
    lod1_obj = leaf_obj.copy()
    lod1_obj.data = leaf_obj.data.copy()
    lod1_obj.name = "ENV_Foliage_Leaves_Scatter_LOD1"
    bpy.context.collection.objects.link(lod1_obj)
    mod1 = lod1_obj.modifiers.new("Decimate", "DECIMATE")
    mod1.ratio = 0.25
    bpy.context.view_layer.objects.active = lod1_obj
    bpy.ops.object.modifier_apply(modifier="Decimate")
    lod1_path = os.path.join(models_dir, "leaves_lod1.glb")
    export_single_mesh(lod1_obj, lod1_path)
    bpy.data.objects.remove(lod1_obj, do_unlink=True)

    # LOD 2 (0.06 decimation)
    lod2_obj = leaf_obj.copy()
    lod2_obj.data = leaf_obj.data.copy()
    lod2_obj.name = "ENV_Foliage_Leaves_Scatter_LOD2"
    bpy.context.collection.objects.link(lod2_obj)
    mod2 = lod2_obj.modifiers.new("Decimate", "DECIMATE")
    mod2.ratio = 0.06
    bpy.context.view_layer.objects.active = lod2_obj
    bpy.ops.object.modifier_apply(modifier="Decimate")
    lod2_path = os.path.join(models_dir, "leaves_lod2.glb")
    export_single_mesh(lod2_obj, lod2_path)
    bpy.data.objects.remove(lod2_obj, do_unlink=True)

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
        "ENV_Sky_Dome",
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

