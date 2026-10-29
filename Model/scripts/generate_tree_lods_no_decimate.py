#region Imports
import os
import sys
import random
from collections import Counter
import bpy
import bmesh
import mathutils
#endregion

#region Types
# Foliage LOD Generation Pipeline:
# - Bark decimation is strictly disabled to prevent boundary edge collapse and tearing.
# - Leaves are segmented into connected component islands (atomic units).
# - Each island is scaled uniformly around its centroid, preventing vertex displacement compounding and aspect ratio distortion.
#endregion

#region Scaffolding
def log_info(msg: str) -> None:
    print(f"[TREE-LOD-NO-DECIMATE] {msg}")

def remove_object_and_mesh(obj_name: str) -> None:
    old = bpy.data.objects.get(obj_name)
    if old:
        mesh = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if mesh and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
#endregion

#region Foliage
def build_tree_lod_island_scaled(
    src_obj: bpy.types.Object,
    name: str,
    location: mathutils.Vector,
    leaf_mat_idx: int,
    target_islands: int,
    leaf_boost: float,
    cull_sticks_mat_idx: int = None,
    collection_name: str = "03_Large_Plants"
) -> bpy.types.Object:
    """
    Builds a tree LOD preserving 100% of LOD0 bark geometry without decimation.
    Processes leaf faces as atomic connected component islands so shared vertices
    are scaled exactly once around the island centroid, maintaining aspect ratio.
    """
    col = bpy.data.collections.get(collection_name)
    remove_object_and_mesh(name)

    mesh = src_obj.data.copy()
    mesh.name = f"{name}_Mesh"
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    col.objects.link(obj)

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    # 1. Cull sticks/petioles if specified
    if cull_sticks_mat_idx is not None:
        stick_faces = [f for f in bm.faces if f.material_index == cull_sticks_mat_idx]
        bmesh.ops.delete(bm, geom=stick_faces, context='FACES')
        bm.faces.ensure_lookup_table()

    # 2. Segment leaf faces into connected component islands
    leaf_faces = [f for f in bm.faces if f.material_index == leaf_mat_idx]
    visited = set()
    islands = []
    for f in leaf_faces:
        if f in visited:
            continue
        isl = []
        q = [f]
        visited.add(f)
        while q:
            curr = q.pop()
            isl.append(curr)
            for e in curr.edges:
                for linked in e.link_faces:
                    if linked not in visited and linked.material_index == leaf_mat_idx:
                        visited.add(linked)
                        q.append(linked)
        islands.append(isl)

    # 3. Subsample and scale islands atomically
    n_islands = len(islands)
    if n_islands > target_islands:
        random.seed(42 + target_islands)
        surviving_indices = set(random.sample(range(n_islands), target_islands))
        to_del_faces = []
        for idx, isl in enumerate(islands):
            if idx in surviving_indices:
                isl_verts = list({v for f in isl for v in f.verts})
                c = sum((v.co for v in isl_verts), mathutils.Vector()) / len(isl_verts)
                for v in isl_verts:
                    v.co = c + (v.co - c) * leaf_boost
            else:
                to_del_faces.extend(isl)
        bmesh.ops.delete(bm, geom=to_del_faces, context='FACES')
    else:
        for isl in islands:
            isl_verts = list({v for f in isl for v in f.verts})
            c = sum((v.co for v in isl_verts), mathutils.Vector()) / len(isl_verts)
            for v in isl_verts:
                v.co = c + (v.co - c) * leaf_boost

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    counts = Counter(f.material_index for f in obj.data.polygons)
    log_info(f"Generated {name} (boost={leaf_boost}x): polys={len(obj.data.polygons)}, verts={len(obj.data.vertices)}, counts={counts}")
    return obj
#endregion

#region Export
def export_selected_glbs(export_manifest: list, gltf_dir: str) -> None:
    os.makedirs(gltf_dir, exist_ok=True)
    for obj_name, glb_filename in export_manifest:
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            log_info(f"WARNING: Object {obj_name} not found!")
            continue

        out_path = os.path.join(gltf_dir, glb_filename)
        orig_loc = obj.location.copy()
        obj.location = (0.0, 0.0, 0.0)
        bpy.context.view_layer.update()

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
            export_lights=False
        )

        obj.location = orig_loc
        bpy.context.view_layer.update()

        size_mb = os.path.getsize(out_path) / (1024 * 1024)
        log_info(f"Exported {obj_name} -> {glb_filename} ({size_mb:.2f} MB)")
#endregion

#region Core
def run_tree_lod_pipeline(repo_root: str) -> None:
    gltf_dir = os.path.join(repo_root, "gltf")
    t1_lod0 = bpy.data.objects.get("Tree_01_LOD0")
    t2_lod0 = bpy.data.objects.get("Tree_02_LOD0")
    aspen_lod0 = bpy.data.objects.get("aspen2_LOD0")
    assert t1_lod0 is not None and t2_lod0 is not None, "Source LOD0 trees missing"

    # Tree 01 (1-quad leaves): LOD1 22k leaves @ 3.2x (16.5cm), LOD2 6k leaves @ 5.5x (28.6cm)
    build_tree_lod_island_scaled(t1_lod0, "Tree_01_LOD1", mathutils.Vector((6.0, 25.0, 0.0)), leaf_mat_idx=3, target_islands=22000, leaf_boost=3.2, cull_sticks_mat_idx=2)
    build_tree_lod_island_scaled(t1_lod0, "Tree_01_LOD2", mathutils.Vector((12.0, 25.0, 0.0)), leaf_mat_idx=3, target_islands=6000, leaf_boost=5.5, cull_sticks_mat_idx=2)

    # Tree 02 (2-quad folded leaves): LOD1 15k islands (30k faces) @ 2.6x (25.8cm), LOD2 4k islands (8k faces) @ 4.2x (41.7cm)
    build_tree_lod_island_scaled(t2_lod0, "Tree_02_LOD1", mathutils.Vector((6.0, 32.0, 0.0)), leaf_mat_idx=2, target_islands=15000, leaf_boost=2.6, cull_sticks_mat_idx=None)
    build_tree_lod_island_scaled(t2_lod0, "Tree_02_LOD2", mathutils.Vector((12.0, 32.0, 0.0)), leaf_mat_idx=2, target_islands=4000, leaf_boost=4.2, cull_sticks_mat_idx=None)

    # Aspen Tree (6-7 face cluster leaves, 57k trunk): LOD1 3.5k islands @ 2.2x, LOD2 1k islands @ 3.8x, 0% trunk decimation
    if aspen_lod0:
        build_tree_lod_island_scaled(aspen_lod0, "aspen2_LOD1", mathutils.Vector((6.0, 18.0, 0.0)), leaf_mat_idx=1, target_islands=3500, leaf_boost=2.2, cull_sticks_mat_idx=None)
        build_tree_lod_island_scaled(aspen_lod0, "aspen2_LOD2", mathutils.Vector((12.0, 18.0, 0.0)), leaf_mat_idx=1, target_islands=1000, leaf_boost=3.8, cull_sticks_mat_idx=None)

    bpy.ops.wm.save_mainfile()
    log_info("Saved asset.blend successfully.")

    manifest = [
        ("Tree_01_LOD1", "tree_01_lod1.glb"),
        ("Tree_01_LOD2", "tree_01_lod2.glb"),
        ("Tree_01_LOD3", "tree_01_lod3.glb"),
        ("Tree_02_LOD1", "tree_02_lod1.glb"),
        ("Tree_02_LOD2", "tree_02_lod2.glb"),
        ("Tree_02_LOD3", "tree_02_lod3.glb"),
        ("aspen2_LOD1", "tree_aspen_lod1.glb"),
        ("aspen2_LOD2", "tree_aspen_lod2.glb"),
        ("aspen2_LOD3", "tree_aspen_lod3.glb"),
    ]
    export_selected_glbs(manifest, gltf_dir)
#endregion

#region Main
if __name__ == "__main__":
    blend_dir = bpy.path.abspath("//")
    root = os.path.abspath(os.path.join(blend_dir, ".."))
    run_tree_lod_pipeline(root)
#endregion
