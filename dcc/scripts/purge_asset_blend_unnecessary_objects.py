#region Imports
import os
import sys
import bpy
#endregion

#region Types
# Purge configuration
class PurgeConfig:
    UNWANTED_COLLECTIONS = [
        "Lamborghini_Revuelto_Detailed_Ref",
        "01_Body_Exterior",
        "02_Aerodynamics",
        "03_Lighting_Glass",
        "04_Powertrain",
        "05_Interior",
        "06_Wheels_Brakes",
        "04_Ground_Surfaces_Ref",
    ]
    UNWANTED_OBJECTS = [
        "ENV_Road_Asphalt_Linear_Ref",
        "ENV_Terrain_Forest_Floor_Uniform_Ref",
    ]
#endregion

#region Scaffolding
def log_step(msg):
    print(f"[PURGE_ASSETS] {msg}")

def remove_collection_recursive(coll):
    for child in list(coll.children):
        remove_collection_recursive(child)
    for obj in list(coll.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(coll)
#endregion

#region Purge
def delete_unnecessary_objects():
    log_step("Deleting unneeded reference objects...")
    for obj_name in PurgeConfig.UNWANTED_OBJECTS:
        obj = bpy.data.objects.get(obj_name)
        if obj:
            log_step(f"Removing object: {obj_name}")
            bpy.data.objects.remove(obj, do_unlink=True)

    log_step("Deleting unneeded reference collections...")
    for coll_name in PurgeConfig.UNWANTED_COLLECTIONS:
        coll = bpy.data.collections.get(coll_name)
        if coll:
            log_step(f"Removing collection and children: {coll_name}")
            remove_collection_recursive(coll)

def purge_orphaned_datablocks():
    log_step("Purging all orphaned meshes, materials, and textures...")
    purged_total = 0
    for _ in range(5):
        res = bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        purged_total += res
        if res == 0:
            break
    log_step(f"Total orphaned data blocks purged: {purged_total}")
#endregion

#region Core
def execute_purge():
    delete_unnecessary_objects()
    purge_orphaned_datablocks()

    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
    log_step(f"Saved optimized & compressed blend file: {blend_path}")
#endregion

#region Main
if __name__ == '__main__':
    execute_purge()
    sys.exit(0)
#endregion

