#region Imports
import math
import os
import sys
from mathutils import Vector
import bpy
#endregion

#region Types
# Transformation parameters container
class TransformConfig:
    CAR_ROTATION_Z = math.radians(90.0)  # Orient along tangent (+Y)
    ROAD_SURFACE_Z = -0.0642018
    TERRAIN_TARGET_Z = -0.0720           # 7.8mm below road surface to eliminate floating cliff
#endregion

#region Scaffolding
def log_step(msg):
    print(f"[BASE_SCENE_FIX] {msg}")
#endregion

#region Transform
def align_car_along_road():
    log_step("Aligning car along the circular road tangent...")
    car_root = bpy.data.objects.get("Revuelto.Body")
    if not car_root:
        raise RuntimeError("Revuelto.Body not found")

    car_root.rotation_euler.z = TransformConfig.CAR_ROTATION_Z
    bpy.context.view_layer.update()

    # Calculate exact contact offset for tires
    tires = bpy.data.objects.get("Revuelto_Wheels_TireTread")
    if tires:
        tire_bb = [tires.matrix_world @ Vector(b) for b in tires.bound_box]
        min_tire_z = min(b.z for b in tire_bb)
        delta_z = TransformConfig.ROAD_SURFACE_Z - min_tire_z
        car_root.location.z += delta_z
        log_step(f"Car snapped to road: min tire Z = {min_tire_z + delta_z:.4f}m (offset {delta_z:.4f}m)")
    else:
        log_step("Warning: Revuelto_Wheels_TireTread not found for tire snapping")

def close_road_terrain_gap():
    log_step("Closing road-to-terrain vertical gap...")
    terrain = bpy.data.objects.get("ENV_Terrain_Forest_Floor_Layered")
    if not terrain:
        raise RuntimeError("ENV_Terrain_Forest_Floor_Layered not found")

    old_z = terrain.location.z
    terrain.location.z = TransformConfig.TERRAIN_TARGET_Z
    bpy.context.view_layer.update()
    log_step(f"Terrain Z adjusted from {old_z:.4f}m to {terrain.location.z:.4f}m (gap closed by {abs(terrain.location.z - old_z):.4f}m)")
#endregion

#region Export
def export_updated_base_scene(out_glb_path):
    log_step(f"Re-exporting updated base scene to {out_glb_path}...")
    bpy.ops.object.select_all(action='DESELECT')

    car_coll = bpy.data.collections.get("Lamborghini_Revuelto")
    car_root = bpy.data.objects.get("Revuelto.Body")
    selected_count = 0

    if car_root:
        car_root.select_set(True)
        selected_count += 1

    if car_coll:
        for obj in car_coll.all_objects:
            if obj.type == 'MESH':
                obj.select_set(True)
                selected_count += 1

    for obj_name in ["ENV_Road_Asphalt_ClosedLoop", "ENV_Terrain_Forest_Floor_Layered"]:
        obj = bpy.data.objects.get(obj_name)
        if obj:
            obj.select_set(True)
            selected_count += 1

    log_step(f"Selected {selected_count} objects for glTF export.")
    bpy.ops.export_scene.gltf(
        filepath=out_glb_path,
        use_selection=True,
        export_format='GLB',
        export_apply=False,
        export_materials='EXPORT',
        export_image_format='AUTO',
        export_cameras=False,
        export_lights=False
    )
    log_step("Updated base_scene.glb export complete.")

def render_verification_image(out_img_path):
    log_step(f"Rendering verification frame to {out_img_path}...")
    scene = bpy.context.scene
    scene.render.filepath = out_img_path
    bpy.ops.render.render(write_still=True)
    log_step("Verification render saved.")
#endregion

#region Core
def execute_alignment_fix():
    align_car_along_road()
    close_road_terrain_gap()

    # Save asset.blend
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    log_step(f"Saved {blend_path}")

    # Export glb
    out_glb = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\gltf\base_scene.glb"
    export_updated_base_scene(out_glb)

    # Render image
    out_img = r"C:\Users\boyce\.gemini\antigravity\brain\722e3f69-5804-4a4b-b54b-ebccc9aed1a5\base_scene_fixed.png"
    render_verification_image(out_img)
#endregion

#region Main
if __name__ == '__main__':
    execute_alignment_fix()
    sys.exit(0)
#endregion

