#region Imports
import os
import sys
import bpy
#endregion

#region Types
class SkyColumnConfig:
    RADIUS = 90.0
    DEPTH = 70.0       # Height of the cylinder
    Z_CENTER = 25.0    # Bottom at Z=-10m, Top at Z=+60m
    SEGMENTS = 48
#endregion

#region Scaffolding
def log_step(msg):
    print(f"[SKY_COLUMN] {msg}")
#endregion

#region Column
def setup_sky_column():
    log_step("Removing old spherical ENV_Sky_Dome...")
    old_dome = bpy.data.objects.get("ENV_Sky_Dome")
    if old_dome:
        bpy.data.objects.remove(old_dome, do_unlink=True)

    old_col = bpy.data.objects.get("ENV_Sky_Column")
    if old_col:
        bpy.data.objects.remove(old_col, do_unlink=True)

    log_step("Creating cylindrical ENV_Sky_Column (Sky Cylinder / Column)...")
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=SkyColumnConfig.SEGMENTS,
        radius=SkyColumnConfig.RADIUS,
        depth=SkyColumnConfig.DEPTH,
        end_fill_type='NOTHING',
        location=(0.0, 0.0, SkyColumnConfig.Z_CENTER)
    )
    col_obj = bpy.context.active_object
    col_obj.name = "ENV_Sky_Column"

    # Link to 04_Ground_Surfaces collection
    ground_coll = bpy.data.collections.get("04_Ground_Surfaces")
    if not ground_coll:
        ground_coll = bpy.context.scene.collection
    if col_obj.name not in ground_coll.objects:
        ground_coll.objects.link(col_obj)
        if col_obj.name in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.unlink(col_obj)

    # Flip normals inward
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode='OBJECT')

    # Setup UV coordinates for seamless 360 degree cylindrical panorama
    mesh = col_obj.data
    uv_layer = mesh.uv_layers.active or mesh.uv_layers.new(name="UVMap")
    mesh.uv_layers.active = uv_layer

    # Assign MAT_ENV_Sky_Column material
    mat_sky = bpy.data.materials.get("MAT_ENV_Sky_Column")
    if not mat_sky:
        mat_sky = bpy.data.materials.new("MAT_ENV_Sky_Column")
    mat_sky.use_nodes = True
    nodes = mat_sky.node_tree.nodes
    nodes.clear()

    node_out = nodes.new(type='ShaderNodeOutputMaterial')
    node_out.location = (400, 0)
    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_bsdf.location = (100, 0)
    mat_sky.node_tree.links.new(node_bsdf.outputs['BSDF'], node_out.inputs['Surface'])

    tex_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\textures\sky_dome_gradient.png"
    img_sky = bpy.data.images.get("sky_dome_gradient.png")
    if img_sky:
        bpy.data.images.remove(img_sky)
    if os.path.exists(tex_path):
        img_sky = bpy.data.images.load(tex_path)
    if img_sky:
        img_sky.pack()
        node_tex = nodes.new(type='ShaderNodeTexImage')
        node_tex.location = (-250, 0)
        node_tex.image = img_sky
        mat_sky.node_tree.links.new(node_tex.outputs['Color'], node_bsdf.inputs['Base Color'])
        if 'Emission Color' in node_bsdf.inputs:
            mat_sky.node_tree.links.new(node_tex.outputs['Color'], node_bsdf.inputs['Emission Color'])
            node_bsdf.inputs['Emission Strength'].default_value = 1.0

    node_bsdf.inputs['Roughness'].default_value = 1.0
    node_bsdf.inputs['Metallic'].default_value = 0.0

    col_obj.data.materials.clear()
    col_obj.data.materials.append(mat_sky)
    log_step("Cylindrical Sky Column successfully created and textured.")
#endregion

#region Export
def export_updated_scene():
    log_step("Exporting base_scene.glb with Sky Column...")
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)

    out_glb = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\gltf\base_scene.glb"
    bpy.ops.object.select_all(action='DESELECT')

    car_root = bpy.data.objects.get("Revuelto.Body")
    if car_root:
        car_root.select_set(True)

    car_coll = bpy.data.collections.get("Lamborghini_Revuelto")
    if car_coll:
        for o in car_coll.all_objects:
            o.select_set(True)

    for name in ["ENV_Road_Asphalt_ClosedLoop", "ENV_Terrain_Forest_Floor_Layered", "ENV_Sky_Column"]:
        o = bpy.data.objects.get(name)
        if o:
            o.select_set(True)

    bpy.ops.export_scene.gltf(
        filepath=out_glb,
        use_selection=True,
        export_format='GLB',
        export_apply=False,
        export_materials='EXPORT',
        export_image_format='AUTO',
        export_cameras=False,
        export_lights=False
    )
    log_step(f"Exported updated scene to {out_glb}")
#endregion

#region Core
def execute():
    setup_sky_column()
    export_updated_scene()
#endregion

#region Main
if __name__ == '__main__':
    execute()
    sys.exit(0)
#endregion
