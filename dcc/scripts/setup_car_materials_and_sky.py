#region Imports
import os
import sys
import bpy
from mathutils import Vector
#endregion

#region Types
# Material configuration container
#endregion

#region Scaffolding
def log_step(msg):
    print(f"[MAT_SKY_PIPELINE] {msg}")

def ensure_principled_mat(mat_name, base_color, metallic, roughness, alpha=1.0, emission=None):
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    node_out = nodes.new(type='ShaderNodeOutputMaterial')
    node_out.location = (300, 0)
    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_bsdf.location = (0, 0)
    mat.node_tree.links.new(node_bsdf.outputs['BSDF'], node_out.inputs['Surface'])

    node_bsdf.inputs['Base Color'].default_value = base_color
    node_bsdf.inputs['Metallic'].default_value = metallic
    node_bsdf.inputs['Roughness'].default_value = roughness
    if 'Alpha' in node_bsdf.inputs:
        node_bsdf.inputs['Alpha'].default_value = alpha

    if emission and 'Emission Color' in node_bsdf.inputs:
        node_bsdf.inputs['Emission Color'].default_value = emission
        if 'Emission Strength' in node_bsdf.inputs:
            node_bsdf.inputs['Emission Strength'].default_value = 1.0

    if alpha < 0.99:
        mat.blend_method = 'BLEND'
    else:
        mat.blend_method = 'OPAQUE'

    return mat
#endregion

#region SkyDome
def create_sky_dome():
    log_step("Creating atmospheric Sky Dome...")
    ground_coll = bpy.data.collections.get("04_Ground_Surfaces")
    if not ground_coll:
        ground_coll = bpy.context.scene.collection

    old_dome = bpy.data.objects.get("ENV_Sky_Dome")
    if old_dome:
        bpy.data.objects.remove(old_dome, do_unlink=True)

    # Create sphere with radius 90m
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=90.0, location=(0.0, 0.0, 0.0))
    sky_obj = bpy.context.active_object
    sky_obj.name = "ENV_Sky_Dome"
    if sky_obj.name not in ground_coll.objects:
        ground_coll.objects.link(sky_obj)
        if sky_obj.name in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.unlink(sky_obj)

    # Flip normals inward so interior is visible
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode='OBJECT')

    # Assign sky gradient material
    mat_sky = bpy.data.materials.get("MAT_ENV_Sky_Dome")
    if not mat_sky:
        mat_sky = bpy.data.materials.new("MAT_ENV_Sky_Dome")
    mat_sky.use_nodes = True
    nodes = mat_sky.node_tree.nodes
    nodes.clear()

    node_out = nodes.new(type='ShaderNodeOutputMaterial')
    node_out.location = (400, 0)
    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_bsdf.location = (100, 0)
    mat_sky.node_tree.links.new(node_bsdf.outputs['BSDF'], node_out.inputs['Surface'])

    # Load sky texture
    tex_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\textures\sky_dome_gradient.png"
    img_sky = bpy.data.images.get("sky_dome_gradient.png")
    if not img_sky and os.path.exists(tex_path):
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

    sky_obj.data.materials.clear()
    sky_obj.data.materials.append(mat_sky)
    log_step("Sky Dome created and textured.")
#endregion

#region CarMaterials
def setup_car_materials():
    log_step("Configuring PBR materials for Revuelto...")
    # 1. Body Paint - Pearl metallic sports car finish
    ensure_principled_mat(
        "Revuelto_Body_Paint",
        base_color=(0.92, 0.93, 0.96, 1.0),
        metallic=0.5,
        roughness=0.18
    )

    # 2. Clear Glass
    ensure_principled_mat(
        "Revuelto_Glass_Clear",
        base_color=(0.06, 0.08, 0.12, 0.25),
        metallic=0.0,
        roughness=0.05,
        alpha=0.25
    )

    # 3. Tinted Glass
    ensure_principled_mat(
        "Revuelto_Glass_Tinted",
        base_color=(0.02, 0.02, 0.03, 0.75),
        metallic=0.1,
        roughness=0.08,
        alpha=0.75
    )

    # 4. Brake Calipers - Racing Red
    ensure_principled_mat(
        "Revuelto_Brakes_Calipers",
        base_color=(0.85, 0.05, 0.02, 1.0),
        metallic=0.25,
        roughness=0.18
    )

    # 5. Headlights - Polycarbonate lenses
    ensure_principled_mat(
        "Revuelto_Lights_Headlights",
        base_color=(0.90, 0.92, 1.0, 0.40),
        metallic=0.1,
        roughness=0.05,
        alpha=0.40
    )

    # 6. Taillights - Translucent red
    ensure_principled_mat(
        "Revuelto_Lights_Taillights",
        base_color=(0.85, 0.02, 0.02, 0.85),
        metallic=0.0,
        roughness=0.15,
        alpha=0.85
    )

    # 7. Aerodynamic Trim - Satin black
    ensure_principled_mat(
        "Revuelto_Trim_Black",
        base_color=(0.025, 0.025, 0.025, 1.0),
        metallic=0.1,
        roughness=0.35
    )

    # 8. Carbon Fiber
    ensure_principled_mat(
        "Revuelto_Carbon_Fiber",
        base_color=(0.04, 0.04, 0.04, 1.0),
        metallic=0.2,
        roughness=0.25
    )

    # 9. Brake Rotors - Carbon ceramic / steel
    ensure_principled_mat(
        "Revuelto_Brakes_Rotors",
        base_color=(0.42, 0.42, 0.42, 1.0),
        metallic=0.85,
        roughness=0.25
    )

    # 10. Tires
    ensure_principled_mat(
        "Revuelto_Wheels_TireTread",
        base_color=(0.02, 0.02, 0.02, 1.0),
        metallic=0.0,
        roughness=0.75
    )
    ensure_principled_mat(
        "Revuelto_Wheels_TireSidewall",
        base_color=(0.02, 0.02, 0.02, 1.0),
        metallic=0.0,
        roughness=0.75
    )
    log_step("Car PBR materials successfully updated.")
#endregion

#region Export
def export_updated_scene():
    log_step("Exporting base_scene.glb...")
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

    for name in ["ENV_Road_Asphalt_ClosedLoop", "ENV_Terrain_Forest_Floor_Layered", "ENV_Sky_Dome"]:
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
    create_sky_dome()
    setup_car_materials()
    export_updated_scene()
#endregion

#region Main
if __name__ == '__main__':
    execute()
    sys.exit(0)
#endregion

