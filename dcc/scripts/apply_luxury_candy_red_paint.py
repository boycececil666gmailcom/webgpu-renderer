#region Imports
import os
import sys
import math
import bpy
#endregion

#region Types
class PaintSpec:
    TEXTURE_PATH = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\textures\metallic_red_paint_flake.png"
    BODY_COLOR_LINEAR = (0.85, 0.018, 0.014, 1.0)
    ACCENT_COLOR_LINEAR = (0.88, 0.022, 0.016, 1.0)
    CALIPER_COLOR_LINEAR = (0.85, 0.018, 0.014, 1.0)
    
    METALLIC = 0.88
    ROUGHNESS = 0.12
    COAT_WEIGHT = 1.0
    COAT_ROUGHNESS = 0.015
    COAT_IOR = 1.54
    SPECULAR_IOR_LEVEL = 0.65
#endregion

#region Scaffolding
def log_step(msg: str) -> None:
    print(f"[LUXURY_RED_PAINT] {msg}")

def setup_body_paint_material(mat_name: str, use_texture: bool = True) -> bpy.types.Material:
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    links = mat.node_tree.links

    out_node = nodes.new(type='ShaderNodeOutputMaterial')
    out_node.location = (600, 0)

    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (200, 0)
    links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

    # Core PBR parameters
    bsdf.inputs['Metallic'].default_value = PaintSpec.METALLIC
    bsdf.inputs['Roughness'].default_value = PaintSpec.ROUGHNESS
    if 'Coat Weight' in bsdf.inputs:
        bsdf.inputs['Coat Weight'].default_value = PaintSpec.COAT_WEIGHT
    if 'Coat Roughness' in bsdf.inputs:
        bsdf.inputs['Coat Roughness'].default_value = PaintSpec.COAT_ROUGHNESS
    if 'Coat IOR' in bsdf.inputs:
        bsdf.inputs['Coat IOR'].default_value = PaintSpec.COAT_IOR
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = PaintSpec.SPECULAR_IOR_LEVEL

    # Set default socket color
    bsdf.inputs['Base Color'].default_value = PaintSpec.BODY_COLOR_LINEAR

    if use_texture and os.path.exists(PaintSpec.TEXTURE_PATH):
        img = bpy.data.images.get("metallic_red_paint_flake.png")
        if not img:
            img = bpy.data.images.load(PaintSpec.TEXTURE_PATH)
        img.pack()
        
        tex_node = nodes.new(type='ShaderNodeTexImage')
        tex_node.location = (-200, 0)
        tex_node.image = img
        links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
        log_step(f"Connected metallic flake texture to '{mat_name}'.")

    mat.blend_method = 'OPAQUE'
    return mat

def setup_calipers_material() -> None:
    mat = bpy.data.materials.get("Revuelto_Brakes_Calipers")
    if not mat:
        return
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    links = mat.node_tree.links

    out_node = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

    bsdf.inputs['Base Color'].default_value = PaintSpec.CALIPER_COLOR_LINEAR
    bsdf.inputs['Metallic'].default_value = 0.25
    bsdf.inputs['Roughness'].default_value = 0.08
    if 'Coat Weight' in bsdf.inputs:
        bsdf.inputs['Coat Weight'].default_value = 1.0
    if 'Coat Roughness' in bsdf.inputs:
        bsdf.inputs['Coat Roughness'].default_value = 0.02
    mat.blend_method = 'OPAQUE'
    log_step("Configured Revuelto_Brakes_Calipers.")
#endregion

#region Domain
def process_blend_file(blend_path: str) -> None:
    log_step(f"Opening {blend_path}...")
    bpy.ops.wm.open_mainfile(filepath=blend_path)

    # 1. Update Body Paint & Red Accents
    setup_body_paint_material("Revuelto_Body_Paint", use_texture=True)
    setup_body_paint_material("Revuelto_Accent_Red", use_texture=True)
    setup_calipers_material()

    # 2. Save blend file
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
    log_step("Saved asset.blend with luxury Rosso Mars metallic candy red paint.")

def export_glb(out_glb: str) -> None:
    log_step(f"Exporting GLB to {out_glb}...")
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
    log_step(f"Successfully exported {out_glb} ({os.path.getsize(out_glb)} bytes)")

def render_preview(out_img: str) -> None:
    log_step(f"Rendering verification frame to {out_img}...")
    cam = bpy.data.objects.get("CAM_Scene_Follow")
    if cam:
        bpy.context.scene.camera = cam

    bpy.context.scene.render.resolution_x = 1920
    bpy.context.scene.render.resolution_y = 1080
    bpy.context.scene.render.filepath = out_img
    bpy.ops.render.render(write_still=True)
    log_step(f"Rendered verification still to {out_img}")
#endregion

#region Core
def execute() -> None:
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    out_glb = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\gltf\base_scene.glb"
    out_img = r"c:\Users\boyce\.gemini\antigravity\brain\722e3f69-5804-4a4b-b54b-ebccc9aed1a5\scratch\blender_luxury_red_verify.png"

    process_blend_file(blend_path)
    export_glb(out_glb)
    render_preview(out_img)
#endregion

#region Main
if __name__ == '__main__':
    execute()
    sys.exit(0)
#endregion

