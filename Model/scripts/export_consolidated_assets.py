#!/usr/bin/env python3
#region Imports
import os
import sys
import bpy
#endregion

#region Types
# Consolidated glTF Multi-Mesh Export Pipeline:
# - Exports sibling LOD meshes together into a single master .glb container per species.
# - Prunes unreferenced Normal, Roughness, and Displacement texture maps during export.
# - Re-centers all meshes to (0, 0, 0) during export so pivot aligns with instance origins.
# - Leaves asset.blend fully in sync and invokes bpy.ops.wm.save_mainfile().
#endregion

#region Scaffolding
def log_info(msg: str) -> None:
    print(f"[CONSOLIDATED-EXPORT] {msg}")

ASSET_GROUPS = {
    "tree_maple.glb": ['Maple_tree1_LOD1', 'Maple_tree1_LOD2', 'Maple_tree1_LOD3'],
    "tree_aspen.glb": ['aspen2_LOD1', 'aspen2_LOD2', 'aspen2_LOD3'],
    "tree_01.glb": ['Tree_01_LOD1', 'Tree_01_LOD2', 'Tree_01_LOD3'],
    "tree_02.glb": ['Tree_02_LOD1', 'Tree_02_LOD2', 'Tree_02_LOD3'],
    "bush_01.glb": ['AE_15TH_FOREST_BUSH_01_LOD1', 'AE_15TH_FOREST_BUSH_01_LOD2', 'AE_15TH_FOREST_BUSH_01_LOD3'],
    "fern_01.glb": ['AE_15TH_FERN_01_LOD1', 'AE_15TH_FERN_01_LOD2', 'AE_15TH_FERN_01_LOD3'],
    "fern_02.glb": ['AE_15TH_FERN_02_LOD1', 'AE_15TH_FERN_02_LOD2', 'AE_15TH_FERN_02_LOD3'],
    "rock_01.glb": ['Rock_01_LOD2', 'Rock_01_LOD3'],
    "rock_02.glb": ['Rock_02_LOD2', 'Rock_02_LOD3'],
    "rock_03.glb": ['Rock_03_LOD2', 'Rock_03_LOD3'],
    "leaves.glb": ['AE_15TH_DRY_LEAVES_01', 'AE_15TH_DRY_LEAVES_02', 'AE_15TH_DRY_LEAVES_03']
}
#endregion

#region Domain
def prune_material_unreferenced_channels(materials):
    removed_links = []
    for mat in materials:
        if not mat or not mat.use_nodes:
            continue
        bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not bsdf:
            continue
        # Unlink Normal and Displacement maps to avoid embedding unused 12K textures into GLB
        for inp_name in ['Normal', 'Displacement', 'Roughness']:
            inp = bsdf.inputs.get(inp_name)
            if inp and inp.is_linked:
                for link in list(inp.links):
                    removed_links.append((mat, inp_name, link.from_socket))
                    mat.node_tree.links.remove(link)
    return removed_links

def restore_material_channels(removed_links):
    for mat, inp_name, from_socket in removed_links:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf:
            mat.node_tree.links.new(from_socket, bsdf.inputs[inp_name])

def export_consolidated_group(glb_filename, obj_names, gltf_dir):
    objs = [bpy.data.objects.get(n) for n in obj_names if bpy.data.objects.get(n)]
    if not objs:
        log_info(f"WARNING: None of objects {obj_names} found for {glb_filename}")
        return

    out_path = os.path.join(gltf_dir, glb_filename)
    
    # Collect all materials used by this group
    group_mats = set()
    for o in objs:
        for s in o.material_slots:
            if s.material:
                group_mats.add(s.material)

    removed_links = prune_material_unreferenced_channels(group_mats)

    orig_locs = {}
    for o in objs:
        orig_locs[o] = o.location.copy()
        o.location = (0.0, 0.0, 0.0)

    bpy.context.view_layer.update()

    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]

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

    for o, loc in orig_locs.items():
        o.location = loc
    bpy.context.view_layer.update()

    restore_material_channels(removed_links)

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    log_info(f"Successfully exported {glb_filename}: {len(objs)} meshes -> {size_mb:.2f} MB")
#endregion

#region Core
def export_all_consolidated_assets(repo_root: str):
    gltf_dir = os.path.join(repo_root, "gltf")
    os.makedirs(gltf_dir, exist_ok=True)

    for glb_filename, obj_names in ASSET_GROUPS.items():
        export_consolidated_group(glb_filename, obj_names, gltf_dir)

    bpy.ops.wm.save_mainfile()
    log_info("Persisted asset.blend successfully.")
#endregion

#region Main
if __name__ == "__main__":
    blend_dir = bpy.path.abspath("//")
    root = os.path.abspath(os.path.join(blend_dir, ".."))
    export_all_consolidated_assets(root)
#endregion

