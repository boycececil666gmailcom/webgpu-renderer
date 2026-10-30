#region Imports
import math
import os
import sys
from mathutils import Vector, Euler
import bpy
#endregion

#region Types
# No custom types needed
#endregion

#region Scaffolding
def log_step(msg):
    print(f"[REEXPORT] {msg}")
#endregion

#region Core
def fix_and_export():
    log_step("Restoring car hierarchy and alignment...")
    car_coll = bpy.data.collections.get("Lamborghini_Revuelto")
    car_root = bpy.data.objects.get("Revuelto.Body")
    if not car_root:
        car_root = bpy.data.objects.new("Revuelto.Body", None)
        car_root.empty_display_type = 'ARROWS'
        car_root.empty_display_size = 2.0
        car_coll.objects.link(car_root)

    car_root.location = Vector((-20.0, 0.0, -0.0929))
    car_root.rotation_euler = Euler((0, 0, math.radians(90.0)), 'XYZ')

    for o in car_coll.objects:
        if o != car_root:
            o.parent = car_root

    bpy.context.view_layer.update()

    tires = bpy.data.objects.get("Revuelto_Wheels_TireTread")
    tire_bb = [tires.matrix_world @ Vector(b) for b in tires.bound_box]
    min_tire_z = min(b.z for b in tire_bb)
    road_z = -0.0642018
    car_root.location.z += (road_z - min_tire_z)

    bpy.context.view_layer.update()
    log_step(f"Car rooted at {car_root.location}, tires at road level {road_z}")

    # Save asset.blend
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
    log_step(f"Saved {blend_path}")

    # Export base_scene.glb
    out_glb = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\gltf\base_scene.glb"
    bpy.ops.object.select_all(action='DESELECT')
    car_root.select_set(True)
    for o in car_coll.all_objects:
        o.select_set(True)

    for name in ["ENV_Road_Asphalt_ClosedLoop", "ENV_Terrain_Forest_Floor_Layered", "CAM_Scene_Follow", "Sun"]:
        o = bpy.data.objects.get(name)
        if o:
            o.select_set(True)

    log_step("Exporting glTF with 1 camera and lights...")
    bpy.ops.export_scene.gltf(
        filepath=out_glb,
        use_selection=True,
        export_format='GLB',
        export_apply=False,
        export_materials='EXPORT',
        export_image_format='AUTO',
        export_cameras=True,
        export_lights=True
    )
    log_step(f"Exported {out_glb}")
#endregion

#region Main
if __name__ == '__main__':
    fix_and_export()
    sys.exit(0)
#endregion

