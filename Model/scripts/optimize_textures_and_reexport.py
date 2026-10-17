#region Imports
import os
import sys
import bpy
#endregion

#region Types
# No custom types needed
#endregion

#region Scaffolding
def log_step(msg):
    print(f"[TEXTURE_OPTIMIZE] {msg}")
#endregion

#region Optimize
def optimize_oversized_textures():
    log_step("Checking and rescaling oversized textures...")
    for img in bpy.data.images:
        w, h = img.size
        if w > 4096 or h > 4096:
            new_w = min(w, 2048) if w > 4096 else w
            new_h = min(h, 256) if h > 4096 else (min(h, 2048) if h > 2048 else h)
            log_step(f"Rescaling {img.name} from {w}x{h} to {new_w}x{new_h}")
            img.scale(new_w, new_h)
#endregion

#region Export
def export_scene(out_glb_path):
    log_step(f"Exporting optimized base_scene to {out_glb_path}...")
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
    log_step("Base Scene export completed.")
#endregion

#region Core
def execute():
    optimize_oversized_textures()
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
    log_step(f"Saved {blend_path}")

    out_glb = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\gltf\base_scene.glb"
    export_scene(out_glb)
#endregion

#region Main
if __name__ == '__main__':
    execute()
    sys.exit(0)
#endregion

