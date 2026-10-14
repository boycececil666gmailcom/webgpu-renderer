#region FixRoadAndBloatModule
import bpy
import bmesh
import math
import os

def log(fn: str, msg: str) -> None:
    print(f"[Optimizer-{fn}] {msg}")

def optimize_road_edges():
    """Dissolves unnecessary radial edges and flips downward normals on the circular road."""
    road_obj = bpy.data.objects.get("ENV_Road_Asphalt_ClosedLoop")
    assert road_obj is not None, "ENV_Road_Asphalt_ClosedLoop not found"
    log("optimize_road_edges", f"Starting road edge optimization on {road_obj.name}")

    if bpy.context.view_layer.objects.active and bpy.context.view_layer.objects.active.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.objects.active = road_obj
    if road_obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    bm = bmesh.new()
    bm.from_mesh(road_obj.data)

    # 1. Flip face normals so they point upwards (+Z)
    log("optimize_road_edges", "Flipping downward normals to point upwards (+Z)")
    bmesh.ops.reverse_faces(bm, faces=bm.faces)

    # 2. Find interior cross edges
    interior_edges = [e for e in bm.edges if not e.is_boundary]
    log("optimize_road_edges", f"Found {len(interior_edges)} interior edges.")

    # Dissolve 3 out of every 4 cross edges: 128 segments -> 32 clean quads (1:1 with 32 UV repeats)
    edges_to_dissolve = [e for i, e in enumerate(interior_edges) if i % 4 != 0]
    log("optimize_road_edges", f"Dissolving {len(edges_to_dissolve)} redundant edges...")
    bmesh.ops.dissolve_edges(bm, edges=edges_to_dissolve, use_verts=True)

    # 3. Clean up normals and recalculate
    bm.normal_update()

    # Re-apply to mesh
    bm.to_mesh(road_obj.data)
    bm.free()
    road_obj.data.update()

    log("optimize_road_edges", f"Road optimization complete: {len(road_obj.data.vertices)} verts, {len(road_obj.data.edges)} edges, {len(road_obj.data.polygons)} faces.")

def purge_scene_bloat():
    """Purges all 14 phantom scenes, 31 orphaned collections, high-poly prebake archives, and unused images."""
    log("purge_scene_bloat", "Starting comprehensive file de-bloat...")

    main_scene = bpy.data.scenes.get("Lamborghini in the forest")
    if not main_scene:
        main_scene = bpy.context.scene
    main_scene.name = "Asset_Library"

    # 1. Remove all phantom scenes
    for s in list(bpy.data.scenes):
        if s != main_scene:
            log("purge_scene_bloat", f"Removing phantom scene: {s.name}")
            bpy.data.scenes.remove(s)

    # 2. Remove 00_Archive_Prebake
    archive_col = bpy.data.collections.get("00_Archive_Prebake")
    if archive_col:
        for o in list(archive_col.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(archive_col)
        log("purge_scene_bloat", "Removed 00_Archive_Prebake.")

    # 3. Valid active asset collections
    active_cols = ['01_Small_Plants', '02_Medium_Plants', '03_Large_Plants', '04_Ground_Surfaces', 'Lamborghini_Revuelto']
    valid_cols = set()
    def gather_cols(c):
        valid_cols.add(c)
        for sub in c.children:
            gather_cols(sub)
    for c_name in active_cols:
        c = bpy.data.collections.get(c_name)
        if c: gather_cols(c)

    # 4. Remove all obsolete/orphaned collections
    for c in list(bpy.data.collections):
        if c not in valid_cols:
            c_name = c.name
            for o in list(c.objects):
                if not o.users_collection or o.users_collection == (c,):
                    bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(c)
            log("purge_scene_bloat", f"Removed obsolete collection: {c_name}")

    # 5. Remove all orphaned objects not in valid collections
    valid_objs = set()
    for c in valid_cols:
        for o in c.objects:
            valid_objs.add(o)
    for o in list(bpy.data.objects):
        if o not in valid_objs and o.name not in ['CAM_Scene_Follow', 'Sun', 'Camera', 'Light']:
            log("purge_scene_bloat", f"Removed orphaned object: {o.name}")
            bpy.data.objects.remove(o, do_unlink=True)

    # 6. Remove unused worlds
    main_world = main_scene.world
    for w in list(bpy.data.worlds):
        if w != main_world:
            bpy.data.worlds.remove(w)

    # 7. Remap duplicate textures (.001, .002) to base texture and remove duplicates
    remap_count = 0
    for img in list(bpy.data.images):
        for suffix in ['.001', '.002', '.003', '.004', '.005', '.006', '.007', '.008', '.009', '.010']:
            if img.name.endswith(suffix):
                base_name = img.name[:-len(suffix)]
                base_img = bpy.data.images.get(base_name)
                if base_img and base_img != img:
                    img.user_remap(base_img)
                    bpy.data.images.remove(img)
                    remap_count += 1
                break
    log("purge_scene_bloat", f"Remapped and eliminated {remap_count} duplicate texture datablocks.")

    # 8. Deep recursive orphan purge
    for i in range(6):
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    log("purge_scene_bloat", f"Purge complete. Remaining meshes: {len(bpy.data.meshes)}, materials: {len(bpy.data.materials)}, images: {len(bpy.data.images)}, node groups: {len(bpy.data.node_groups)}")

def execute():
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    log("execute", f"Opening {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=blend_path)

    orig_bytes = os.path.getsize(blend_path)

    # Step 1: Optimize circle road edges
    optimize_road_edges()

    # Step 2: Purge 14 phantom scenes, 31 collections, and duplicate images
    purge_scene_bloat()

    # Step 3: Save compressed blend file
    log("execute", "Saving compressed asset.blend...")
    bpy.ops.wm.save_mainfile(filepath=blend_path, compress=True)

    new_bytes = os.path.getsize(blend_path)
    log("execute", f"Successfully reduced asset.blend from {orig_bytes/(1024*1024):.2f} MB to {new_bytes/(1024*1024):.2f} MB!")
    print(f"[Optimizer-execute] Slashed file size by {(orig_bytes - new_bytes)/(1024*1024):.2f} MB ({(1 - new_bytes/orig_bytes)*100:.1f}% reduction)!")

if __name__ == "__main__":
    execute()
#endregion
