#region Imports
import os
import sys
import bpy
#endregion

#region Types
class MetallicPaintConfig:
    # Iconic Rosso Mars / Candy Apple Metallic Red
    FLOP_COLOR = (0.28, 0.012, 0.008, 1.0)    # Deep shadow edge
    MID_COLOR = (0.75, 0.035, 0.020, 1.0)     # Body curve midtone
    PEAK_COLOR = (0.92, 0.065, 0.030, 1.0)    # High-angle facing highlight

    METALLIC = 0.88
    ROUGHNESS = 0.12
    COAT_WEIGHT = 1.0
    COAT_ROUGHNESS = 0.015
    COAT_IOR = 1.56
    SPECULAR_IOR_LEVEL = 0.65
#endregion

#region Scaffolding
def log_step(msg: str) -> None:
    print(f"[METALLIC_CAR_PAINT] {msg}")

def build_advanced_metallic_paint_material(mat_name: str) -> bpy.types.Material:
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    links = mat.node_tree.links

    # 1. Output Node
    node_out = nodes.new(type='ShaderNodeOutputMaterial')
    node_out.location = (800, 0)

    # 2. Main Principled BSDF
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (450, 0)
    links.new(bsdf.outputs['BSDF'], node_out.inputs['Surface'])

    # 3. Flop / Flake Travel effect using Layer Weight (Facing)
    layer_weight = nodes.new(type='ShaderNodeLayerWeight')
    layer_weight.location = (-400, 150)
    layer_weight.inputs['Blend'].default_value = 0.45

    color_ramp = nodes.new(type='ShaderNodeValToRGB')
    color_ramp.location = (-150, 150)
    # Configure 3-stage automotive metallic gradient
    color_ramp.color_ramp.elements[0].position = 0.0
    color_ramp.color_ramp.elements[0].color = MetallicPaintConfig.FLOP_COLOR

    color_ramp.color_ramp.elements[1].position = 1.0
    color_ramp.color_ramp.elements[1].color = MetallicPaintConfig.PEAK_COLOR

    elem_mid = color_ramp.color_ramp.elements.new(0.50)
    elem_mid.color = MetallicPaintConfig.MID_COLOR

    links.new(layer_weight.outputs['Facing'], color_ramp.inputs['Fac'])

    # 4. Metallic flake sparkle (High-frequency procedural Voronoi micro-sparkle)
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (-650, -150)

    voronoi = nodes.new(type='ShaderNodeTexVoronoi')
    voronoi.location = (-400, -150)
    voronoi.inputs['Scale'].default_value = 850.0 # Fine micro-flake size
    links.new(tex_coord.outputs['Object'], voronoi.inputs['Vector'])

    # Subtle flake blend: mixes 92% base gradient + 8% micro-sparkle
    mix_flake = nodes.new(type='ShaderNodeMix')
    mix_flake.data_type = 'RGBA'
    mix_flake.location = (150, 100)
    mix_flake.blend_type = 'ADD'
    mix_flake.inputs['Factor'].default_value = 0.12
    links.new(color_ramp.outputs['Color'], mix_flake.inputs[6]) # A
    links.new(voronoi.outputs['Color'], mix_flake.inputs[7])    # B

    # Connect to Principled BSDF Base Color
    links.new(mix_flake.outputs[2], bsdf.inputs['Base Color'])

    # 5. Core Automotive PBR Parameters
    bsdf.inputs['Metallic'].default_value = MetallicPaintConfig.METALLIC
    bsdf.inputs['Roughness'].default_value = MetallicPaintConfig.ROUGHNESS
    if 'Coat Weight' in bsdf.inputs:
        bsdf.inputs['Coat Weight'].default_value = MetallicPaintConfig.COAT_WEIGHT
    if 'Coat Roughness' in bsdf.inputs:
        bsdf.inputs['Coat Roughness'].default_value = MetallicPaintConfig.COAT_ROUGHNESS
    if 'Coat IOR' in bsdf.inputs:
        bsdf.inputs['Coat IOR'].default_value = MetallicPaintConfig.COAT_IOR
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = MetallicPaintConfig.SPECULAR_IOR_LEVEL

    mat.blend_method = 'OPAQUE'
    log_step(f"Successfully constructed multi-layer metallic paint shader for '{mat_name}'.")
    return mat
#endregion

#region Domain
def setup_materials():
    log_step("Updating vehicle metallic paint in asset.blend...")
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    
    # Apply to both main body paint and red accents
    build_advanced_metallic_paint_material("Revuelto_Body_Paint")
    build_advanced_metallic_paint_material("Revuelto_Accent_Red")

    # Ensure other baked materials (carbon, trims, wheels, tires, brakes) remain cleanly configured
    log_step("Verifying auxiliary parts...")

    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
    log_step("Saved asset.blend with updated multi-layer metallic car paint.")

def export_scene(out_glb = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\gltf\base_scene.glb"):
    log_step("Exporting base_scene.glb...")
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
    log_step(f"Successfully exported {out_glb}")
#endregion

#region Core
def run():
    setup_materials()
    export_scene()
#endregion

#region Main
if __name__ == '__main__':
    run()
#endregion

