#region Imports
import bpy
import bmesh
import os
from pathlib import Path
#endregion

#region Scaffolding
def log(fn: str, msg: str) -> None:
    print(f"[AssetLibrary-{fn}] {msg}")

def optimize_ground_and_road(lambo_blend_path: str, temp_export_path: str) -> None:
    """Extracts, simplifies, and creates glTF PBR materials for road and floor from Lamborghini blend."""
    log("optimize_ground_and_road", f"Opening {lambo_blend_path}")
    bpy.ops.wm.open_mainfile(filepath=lambo_blend_path)

    # 1. Road Optimization
    road = bpy.data.objects.get("ENV_Road_Asphalt")
    assert road is not None, "ENV_Road_Asphalt not found"

    # Remove subsurf
    for m in list(road.modifiers):
        if m.type == 'SUBSURF':
            road.modifiers.remove(m)
            log("optimize_ground_and_road", "Removed Subdivision modifier from road.")

    # Apply decimate modifier
    dec_mod = road.modifiers.new("Decimate", 'DECIMATE')
    dec_mod.decimate_type = 'COLLAPSE'
    dec_mod.ratio = 0.12 # Reduces ~4368 faces down to ~800 faces
    
    deps = bpy.context.evaluated_depsgraph_get()
    eval_mesh = bpy.data.meshes.new_from_object(road.evaluated_get(deps))
    road.modifiers.clear()
    road.data = eval_mesh

    # Scale UVs by 18.0 directly on mesh to eliminate procedural mapping nodes
    bm = bmesh.new()
    bm.from_mesh(road.data)
    uv_layer = bm.loops.layers.uv.verify()
    for face in bm.faces:
        for loop in face.loops:
            loop[uv_layer].uv *= 18.0
    bm.to_mesh(road.data)
    bm.free()
    log("optimize_ground_and_road", f"Road optimized: {len(road.data.vertices)} verts, {len(road.data.polygons)} faces.")

    # 2. Terrain Optimization
    terrain = bpy.data.objects.get("ENV_Terrain_Forest_Floor")
    assert terrain is not None, "ENV_Terrain_Forest_Floor not found"

    # Clear scatter vertex groups that prevent polygon reduction
    terrain.vertex_groups.clear()

    # Collapse decimate to clean low-poly surface (~250 faces)
    dec_t = terrain.modifiers.new("Decimate", 'DECIMATE')
    dec_t.decimate_type = 'COLLAPSE'
    dec_t.ratio = 0.01

    deps = bpy.context.evaluated_depsgraph_get()
    eval_mesh_t = bpy.data.meshes.new_from_object(terrain.evaluated_get(deps))
    terrain.modifiers.clear()
    terrain.data = eval_mesh_t

    # Scale UVs by 15.0 directly on mesh to eliminate procedural mapping nodes
    bm_t = bmesh.new()
    bm_t.from_mesh(terrain.data)
    uv_layer_t = bm_t.loops.layers.uv.verify()
    for face in bm_t.faces:
        for loop in face.loops:
            loop[uv_layer_t].uv *= 15.0
    bm_t.to_mesh(terrain.data)
    bm_t.free()
    log("optimize_ground_and_road", f"Terrain optimized: {len(terrain.data.vertices)} verts, {len(terrain.data.polygons)} faces.")

    # 3. Clean glTF 2.0 PBR Materials
    def build_gltf_mat(mat_name, albedo_name, rough_name, norm_name):
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        out_node = nodes.new("ShaderNodeOutputMaterial")
        out_node.location = (400, 0)

        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)
        bsdf.inputs["Metallic"].default_value = 0.0
        links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])

        # Base Color
        albedo_img = bpy.data.images.get(albedo_name)
        if albedo_img:
            tex_albedo = nodes.new("ShaderNodeTexImage")
            tex_albedo.location = (-400, 200)
            tex_albedo.image = albedo_img
            links.new(tex_albedo.outputs["Color"], bsdf.inputs["Base Color"])

        # Roughness
        rough_img = bpy.data.images.get(rough_name)
        if rough_img:
            tex_rough = nodes.new("ShaderNodeTexImage")
            tex_rough.location = (-400, -100)
            tex_rough.image = rough_img
            links.new(tex_rough.outputs["Color"], bsdf.inputs["Roughness"])

        # Normal Map
        norm_img = bpy.data.images.get(norm_name)
        if norm_img:
            tex_norm = nodes.new("ShaderNodeTexImage")
            tex_norm.location = (-400, -400)
            tex_norm.image = norm_img

            norm_map = nodes.new("ShaderNodeNormalMap")
            norm_map.location = (-150, -400)
            links.new(tex_norm.outputs["Color"], norm_map.inputs["Color"])
            links.new(norm_map.outputs["Normal"], bsdf.inputs["Normal"])

        return mat

    mat_road = build_gltf_mat("MAT_ENV_Road_Asphalt_glTF", "vdqhahk_4K_Albedo.jpg", "vdqhahk_4K_Roughness.jpg", "vdqhahk_4K_Normal.jpg")
    mat_terrain = build_gltf_mat("MAT_ENV_Forest_Floor_glTF", "vl4led3lw_4K_Albedo.jpg", "vl4led3lw_4K_Roughness.jpg", "vl4led3lw_4K_Normal.jpg")

    road.data.materials.clear()
    road.data.materials.append(mat_road)

    terrain.data.materials.clear()
    terrain.data.materials.append(mat_terrain)

    # Save to temp export blend
    # Create isolated collection for export
    export_col = bpy.data.collections.new("04_Ground_Surfaces")
    bpy.context.scene.collection.children.link(export_col)
    export_col.objects.link(road)
    export_col.objects.link(terrain)

    log("optimize_ground_and_road", f"Saving intermediate ground data to {temp_export_path}")
    bpy.ops.wm.save_as_mainfile(filepath=temp_export_path)

def assemble_unified_asset_library(bushes_blend_path: str, temp_ground_path: str, target_asset_blend_path: str) -> None:
    """Assembles all plant LODs and the optimized ground surfaces into asset.blend."""
    log("assemble_unified_asset_library", f"Opening {bushes_blend_path}")
    bpy.ops.wm.open_mainfile(filepath=bushes_blend_path)

    # Append 04_Ground_Surfaces from temp_ground_path
    log("assemble_unified_asset_library", f"Appending 04_Ground_Surfaces from {temp_ground_path}")
    with bpy.data.libraries.load(temp_ground_path, link=False) as (data_from, data_to):
        data_to.collections = ["04_Ground_Surfaces"]
        data_to.objects = ["ENV_Road_Asphalt", "ENV_Terrain_Forest_Floor"]
        data_to.materials = ["MAT_ENV_Road_Asphalt_glTF", "MAT_ENV_Forest_Floor_glTF"]
        data_to.images = [
            "vdqhahk_4K_Albedo.jpg", "vdqhahk_4K_Roughness.jpg", "vdqhahk_4K_Normal.jpg",
            "vl4led3lw_4K_Albedo.jpg", "vl4led3lw_4K_Roughness.jpg", "vl4led3lw_4K_Normal.jpg"
        ]

    for col in data_to.collections:
        if col and col.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(col)

    # Ensure road and terrain are properly in 04_Ground_Surfaces
    ground_col = bpy.data.collections.get("04_Ground_Surfaces")
    if ground_col:
        for obj_name in ["ENV_Road_Asphalt", "ENV_Terrain_Forest_Floor"]:
            obj = bpy.data.objects.get(obj_name)
            if obj and obj.name not in ground_col.objects:
                ground_col.objects.link(obj)

    # Clean up empty placeholder collections
    for c in list(bpy.data.collections):
        if len(c.objects) == 0 and c.name not in ["01_Small_Plants", "02_Medium_Plants", "03_Large_Plants", "04_Ground_Surfaces", "00_Archive_Prebake"]:
            bpy.data.collections.remove(c)

    # Pack all textures to make asset.blend 100% self-contained
    try:
        bpy.ops.file.pack_all()
        log("assemble_unified_asset_library", "Packed all texture images into blend file.")
    except Exception as e:
        log("assemble_unified_asset_library", f"Pack warning: {e}")

    # Save to target asset.blend
    bpy.ops.wm.save_as_mainfile(filepath=target_asset_blend_path)
    log("assemble_unified_asset_library", f"Successfully created unified asset library: {target_asset_blend_path}")

    # Remove temporary ground blend file
    if os.path.exists(temp_ground_path):
        os.remove(temp_ground_path)
        log("assemble_unified_asset_library", "Cleaned up temporary export file.")
#endregion

#region Core
def main() -> None:
    base_dir = Path("c:/Users/boyce/OneDrive/Desktop/webgpu-renderer/Model")
    lambo_blend = str(base_dir / "Lamborghini in the forest.blend")
    bushes_blend = str(base_dir / "Bushes_LOD.blend")
    temp_ground = str(base_dir / "_temp_ground_optimized.blend")
    target_asset_blend = str(base_dir / "asset.blend")

    optimize_ground_and_road(lambo_blend, temp_ground)
    assemble_unified_asset_library(bushes_blend, temp_ground, target_asset_blend)

if __name__ == "__main__":
    main()
#endregion

