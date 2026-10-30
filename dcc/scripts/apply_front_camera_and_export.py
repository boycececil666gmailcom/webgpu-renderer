#region Imports
import math
import os
import sys
import bpy
from mathutils import Vector
#endregion

#region Types
class SceneConfig:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    BLEND_PATH = os.path.join(PROJECT_ROOT, "Model", "asset.blend")
    GLB_PATH = os.path.join(PROJECT_ROOT, "assets", "models", "base_scene.glb")
    
    # Camera low-angle hero shot coordinates revealing canopy
    CAM_LOC = Vector((-50.6841, 10.8906, 1.35))
    CAM_TARGET = Vector((-44.4, 2.23, 1.15))
    PITCH_OFFSET_DEG = 2.5
    
    ENV_OBJECTS = [
        "ENV_Road_Asphalt_ClosedLoop",
        "ENV_Terrain_Forest_Floor_Layered",
        "ENV_Sky_Dome",
        "CAM_Scene_Follow",
        "Sun"
    ]
#endregion

#region Scaffolding
def log_step(msg: str):
    print(f"[CAM_DCC] {msg}")
#endregion

#region Camera
def configure_camera():
    log_step("Configuring CAM_Scene_Follow for front-facing hero view...")
    cam_obj = bpy.data.objects.get("CAM_Scene_Follow") or bpy.data.objects.get("Camera")
    if not cam_obj:
        raise RuntimeError("No scene camera object found!")
    cam_obj.name = "CAM_Scene_Follow"
    bpy.context.scene.camera = cam_obj

    # Remove any existing track-to constraints to prevent interference
    for c in list(cam_obj.constraints):
        cam_obj.constraints.remove(c)

    # Set position
    cam_obj.location = SceneConfig.CAM_LOC

    # Point at the car with upward pitch offset to capture canopy
    direction = (SceneConfig.CAM_TARGET - SceneConfig.CAM_LOC).normalized()
    rot_quat = direction.to_track_quat('-Z', 'Y')
    rot_mat = rot_quat.to_matrix().to_4x4()
    from mathutils import Matrix
    pitch_mat = Matrix.Rotation(math.radians(SceneConfig.PITCH_OFFSET_DEG), 4, 'X')
    cam_obj.rotation_euler = (rot_mat @ pitch_mat).to_euler()

    cam_data = cam_obj.data
    cam_data.lens = 30.0
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.1
    cam_data.clip_end = 300.0

    bpy.context.view_layer.update()
    log_step(f"Camera placed at {cam_obj.location}, rot_deg={[round(math.degrees(a), 2) for a in cam_obj.rotation_euler]}")
#endregion

#region Export
def save_and_export_glb():
    log_step(f"Saving blend file to {SceneConfig.BLEND_PATH}...")
    bpy.ops.wm.save_as_mainfile(filepath=SceneConfig.BLEND_PATH, compress=True)

    log_step("Selecting objects for glTF export...")
    bpy.ops.object.select_all(action='DESELECT')

    # Select car hierarchy
    car_root = bpy.data.objects.get("Revuelto.Body")
    car_coll = bpy.data.collections.get("Lamborghini_Revuelto")
    if car_root:
        car_root.select_set(True)
    if car_coll:
        for obj in car_coll.all_objects:
            obj.select_set(True)

    # Select environment, lights, and camera
    for name in SceneConfig.ENV_OBJECTS:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.select_set(True)
            log_step(f"Selected: {name}")
        else:
            log_step(f"Warning: Object '{name}' not found!")

    selected_names = [o.name for o in bpy.context.selected_objects]
    log_step(f"Total objects selected for export: {len(selected_names)}")

    log_step(f"Exporting glTF to {SceneConfig.GLB_PATH}...")
    bpy.ops.export_scene.gltf(
        filepath=SceneConfig.GLB_PATH,
        use_selection=True,
        export_format='GLB',
        export_apply=False,
        export_materials='EXPORT',
        export_image_format='AUTO',
        export_cameras=True,
        export_lights=True
    )
    log_step(f"Successfully exported {SceneConfig.GLB_PATH}")
#endregion

#region Core
def orchestrate_front_camera_update():
    configure_camera()
    save_and_export_glb()
#endregion

#region Main
if __name__ == '__main__':
    orchestrate_front_camera_update()
    sys.exit(0)
#endregion
