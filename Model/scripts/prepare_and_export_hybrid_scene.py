#region Imports
import json
import os
import sys
from mathutils import Vector
import bpy
#endregion

#region Types
# Manifest metadata container for foliage prototypes
class FoliageMeta:
    def __init__(self, name, lods, bbox, recommended_params):
        self.name = name
        self.lods = lods
        self.bbox = bbox
        self.recommended_params = recommended_params

    def to_dict(self):
        return {
            "name": self.name,
            "lods": self.lods,
            "bbox": self.bbox,
            "recommended_params": self.recommended_params
        }
#endregion

#region Scaffolding
def log_step(msg):
    print(f"[HYBRID_PIPELINE] {msg}")

def ensure_collection(name, parent_coll=None):
    coll = bpy.data.collections.get(name)
    if not coll:
        coll = bpy.data.collections.new(name)
        if parent_coll:
            parent_coll.children.link(coll)
        else:
            bpy.context.scene.collection.children.link(coll)
    return coll
#endregion

#region Organize
def organize_ground_references():
    log_step("Organizing ground reference objects...")
    ground_coll = bpy.data.collections.get("04_Ground_Surfaces")
    if not ground_coll:
        return

    ref_coll = ensure_collection("04_Ground_Surfaces_Ref", parent_coll=None)
    ref_coll.hide_render = True
    ref_coll.hide_viewport = True

    ref_names = ["ENV_Road_Asphalt_Linear_Ref", "ENV_Terrain_Forest_Floor_Uniform_Ref"]
    for name in ref_names:
        obj = bpy.data.objects.get(name)
        if obj:
            if obj.name not in ref_coll.objects:
                ref_coll.objects.link(obj)
            if obj.name in ground_coll.objects:
                ground_coll.objects.unlink(obj)
            log_step(f"Moved {name} to {ref_coll.name}")

def prepare_foliage_prototypes_collection():
    log_step("Preparing dedicated Foliage_Prototypes collection with zeroed origins...")
    proto_coll = ensure_collection("Foliage_Prototypes", parent_coll=None)
    
    plant_groups = {
        "Fern_01": ["AE_15TH_FERN_01_LOD0", "AE_15TH_FERN_01_LOD1", "AE_15TH_FERN_01_LOD2", "AE_15TH_FERN_01_LOD3"],
        "Fern_02": ["AE_15TH_FERN_02_LOD0", "AE_15TH_FERN_02_LOD1", "AE_15TH_FERN_02_LOD2", "AE_15TH_FERN_02_LOD3"],
        "Bush_01": ["AE_15TH_FOREST_BUSH_01_LOD0", "AE_15TH_FOREST_BUSH_01_LOD1", "AE_15TH_FOREST_BUSH_01_LOD2", "AE_15TH_FOREST_BUSH_01_LOD3"],
        "Bush_02": ["AE_15TH_FOREST_BUSH_02_LOD0", "AE_15TH_FOREST_BUSH_02_LOD1", "AE_15TH_FOREST_BUSH_02_LOD2", "AE_15TH_FOREST_BUSH_02_LOD3"],
        "Maple_Tree": ["Maple_tree1_LOD0", "Maple_tree1_LOD1", "Maple_tree1_LOD2", "Maple_tree1_LOD3"],
        "Aspen_Tree": ["aspen2_LOD0", "aspen2_LOD1", "aspen2_LOD2", "aspen2_LOD3"],
    }

    manifest = []

    for group_name, lod_names in plant_groups.items():
        lod_entries = []
        max_bb = {"width": 0.0, "depth": 0.0, "height": 0.0}

        for lod_idx, obj_name in enumerate(lod_names):
            src_obj = bpy.data.objects.get(obj_name)
            if not src_obj or src_obj.type != 'MESH':
                continue

            proto_name = f"Proto_{group_name}_LOD{lod_idx}"
            proto_obj = bpy.data.objects.get(proto_name)
            if not proto_obj:
                proto_obj = bpy.data.objects.new(proto_name, src_obj.data)
                proto_coll.objects.link(proto_obj)
            else:
                proto_obj.data = src_obj.data

            proto_obj.location = Vector((0.0, 0.0, 0.0))
            proto_obj.rotation_euler = Vector((0.0, 0.0, 0.0))
            proto_obj.scale = Vector((1.0, 1.0, 1.0))

            bb = [Vector(b) for b in src_obj.bound_box]
            w = max(b.x for b in bb) - min(b.x for b in bb)
            d = max(b.y for b in bb) - min(b.y for b in bb)
            h = max(b.z for b in bb) - min(b.z for b in bb)
            if w > max_bb["width"]: max_bb["width"] = round(w, 3)
            if d > max_bb["depth"]: max_bb["depth"] = round(d, 3)
            if h > max_bb["height"]: max_bb["height"] = round(h, 3)

            vert_count = len(src_obj.data.vertices)
            poly_count = len(src_obj.data.polygons)
            mats = [m.name for m in src_obj.data.materials if m]

            lod_entries.append({
                "lod": lod_idx,
                "object_name": proto_name,
                "mesh_name": src_obj.data.name,
                "vertices": vert_count,
                "triangles": poly_count,
                "materials": mats
            })

        if "Tree" in group_name:
            rec_params = {
                "category": "tree",
                "min_road_dist": 4.5,
                "max_road_dist": 45.0,
                "scale_min": 0.8,
                "scale_max": 1.4,
                "poisson_radius": 5.0,
                "height_growth_factor": 1.5
            }
        elif "Bush" in group_name:
            rec_params = {
                "category": "bush",
                "min_road_dist": 2.2,
                "max_road_dist": 35.0,
                "scale_min": 0.7,
                "scale_max": 1.2,
                "poisson_radius": 2.5,
                "height_growth_factor": 1.1
            }
        else:
            rec_params = {
                "category": "fern_grass",
                "min_road_dist": 1.2,
                "max_road_dist": 30.0,
                "scale_min": 0.6,
                "scale_max": 1.3,
                "poisson_radius": 1.0,
                "height_growth_factor": 1.0
            }

        meta = FoliageMeta(group_name, lod_entries, max_bb, rec_params)
        manifest.append(meta.to_dict())

    return manifest
#endregion

#region Export
def export_base_scene(output_path):
    log_step(f"Exporting Base Scene to {output_path}...")
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

    log_step(f"Selected {selected_count} objects for Base Scene export.")
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        use_selection=True,
        export_format='GLB',
        export_apply=False,
        export_materials='EXPORT',
        export_image_format='AUTO',
        export_cameras=False,
        export_lights=False
    )
    log_step("Base Scene export completed.")

def export_foliage_prototypes(output_path):
    log_step(f"Exporting Foliage Prototypes to {output_path}...")
    bpy.ops.object.select_all(action='DESELECT')

    proto_coll = bpy.data.collections.get("Foliage_Prototypes")
    if not proto_coll:
        raise RuntimeError("Foliage_Prototypes collection not found")

    selected_count = 0
    for obj in proto_coll.objects:
        obj.select_set(True)
        selected_count += 1

    log_step(f"Selected {selected_count} prototype objects for export.")
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        use_selection=True,
        export_format='GLB',
        export_apply=False,
        export_materials='EXPORT',
        export_image_format='AUTO',
        export_cameras=False,
        export_lights=False
    )
    log_step("Foliage Prototypes export completed.")

def save_manifest(manifest_data, manifest_path):
    log_step(f"Saving manifest metadata to {manifest_path}...")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest_data, f, indent=2)
    log_step("Manifest successfully saved.")
#endregion

#region Core
def execute_pipeline():
    out_dir = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\gltf"
    os.makedirs(out_dir, exist_ok=True)
    base_glb = os.path.join(out_dir, "base_scene.glb")
    foliage_glb = os.path.join(out_dir, "foliage_prototypes.glb")
    manifest_json = os.path.join(out_dir, "foliage_manifest.json")

    organize_ground_references()
    manifest_data = prepare_foliage_prototypes_collection()
    
    export_base_scene(base_glb)
    export_foliage_prototypes(foliage_glb)
    save_manifest(manifest_data, manifest_json)

    # Save asset.blend with updated collections
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    log_step(f"Updated and saved {blend_path}")
#endregion

#region Main
if __name__ == '__main__':
    execute_pipeline()
    sys.exit(0)
#endregion

