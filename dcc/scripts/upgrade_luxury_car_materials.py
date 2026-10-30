#region Imports
import os
import sys
import bpy
#endregion

#region Types
class MaterialSpec:
    def __init__(self, name, base_color, metallic, roughness, alpha=1.0, 
                 coat_weight=0.0, coat_roughness=0.03, 
                 transmission=0.0, emission=None, emission_strength=1.0):
        self.name = name
        self.base_color = base_color
        self.metallic = metallic
        self.roughness = roughness
        self.alpha = alpha
        self.coat_weight = coat_weight
        self.coat_roughness = coat_roughness
        self.transmission = transmission
        self.emission = emission
        self.emission_strength = emission_strength
#endregion

#region Scaffolding
def log_step(msg: str) -> None:
    print(f"[LUXURY_CAR_MAT] {msg}")

def apply_material_spec(spec: MaterialSpec) -> bpy.types.Material:
    mat = bpy.data.materials.get(spec.name)
    if not mat:
        mat = bpy.data.materials.new(name=spec.name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    node_out = nodes.new(type='ShaderNodeOutputMaterial')
    node_out.location = (400, 0)
    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_bsdf.location = (0, 0)
    mat.node_tree.links.new(node_bsdf.outputs['BSDF'], node_out.inputs['Surface'])

    # Assign core PBR inputs
    if 'Base Color' in node_bsdf.inputs:
        node_bsdf.inputs['Base Color'].default_value = spec.base_color
    if 'Metallic' in node_bsdf.inputs:
        node_bsdf.inputs['Metallic'].default_value = spec.metallic
    if 'Roughness' in node_bsdf.inputs:
        node_bsdf.inputs['Roughness'].default_value = spec.roughness
    if 'Alpha' in node_bsdf.inputs:
        node_bsdf.inputs['Alpha'].default_value = spec.alpha
    if 'Coat Weight' in node_bsdf.inputs:
        node_bsdf.inputs['Coat Weight'].default_value = spec.coat_weight
    if 'Coat Roughness' in node_bsdf.inputs:
        node_bsdf.inputs['Coat Roughness'].default_value = spec.coat_roughness
    if 'Transmission Weight' in node_bsdf.inputs:
        node_bsdf.inputs['Transmission Weight'].default_value = spec.transmission
    if spec.emission and 'Emission Color' in node_bsdf.inputs:
        node_bsdf.inputs['Emission Color'].default_value = spec.emission
        if 'Emission Strength' in node_bsdf.inputs:
            node_bsdf.inputs['Emission Strength'].default_value = spec.emission_strength

    # Blend mode setup
    if spec.alpha < 0.99 or spec.transmission > 0.01:
        mat.blend_method = 'BLEND'
        if hasattr(mat, 'shadow_method'):
            mat.shadow_method = 'HASHED'
    else:
        mat.blend_method = 'OPAQUE'
        if hasattr(mat, 'shadow_method'):
            mat.shadow_method = 'OPAQUE'

    return mat
#endregion

#region Domain
def configure_all_luxury_materials() -> None:
    log_step("Configuring showroom-grade luxury materials for Lamborghini Revuelto...")

    specs = [
        # 1. Lamborghini Revuelto Flagship Paint: Arancio Apodis / Candy Pearl Red
        MaterialSpec(
            name="Revuelto_Body_Paint",
            base_color=(0.90, 0.12, 0.02, 1.0),
            metallic=0.78,
            roughness=0.08,
            coat_weight=1.0,
            coat_roughness=0.02
        ),
        # 2. Accent Panels & Aero Flares
        MaterialSpec(
            name="Revuelto_Accent_Red",
            base_color=(0.92, 0.14, 0.03, 1.0),
            metallic=0.80,
            roughness=0.08,
            coat_weight=1.0,
            coat_roughness=0.02
        ),
        # 3. Automotive Clear Safety Glass (Windshield, Cockpit)
        MaterialSpec(
            name="Revuelto_Glass_Clear",
            base_color=(0.08, 0.12, 0.16, 0.20),
            metallic=0.05,
            roughness=0.02,
            alpha=0.20,
            coat_weight=1.0,
            coat_roughness=0.01,
            transmission=0.85
        ),
        # 4. Privacy Tinted Glass (Engine Cover, Quarter Glass)
        MaterialSpec(
            name="Revuelto_Glass_Tinted",
            base_color=(0.02, 0.025, 0.03, 0.65),
            metallic=0.10,
            roughness=0.04,
            alpha=0.65,
            coat_weight=1.0,
            coat_roughness=0.02,
            transmission=0.40
        ),
        # 5. Gloss Carbon Fiber Monocoque & Aero Diffusers
        MaterialSpec(
            name="Revuelto_Carbon_Fiber",
            base_color=(0.025, 0.025, 0.025, 1.0),
            metallic=0.35,
            roughness=0.14,
            coat_weight=0.85,
            coat_roughness=0.03
        ),
        # 6. Satin Black Aerodynamic Splitters & Grilles
        MaterialSpec(
            name="Revuelto_Trim_Black",
            base_color=(0.018, 0.018, 0.018, 1.0),
            metallic=0.15,
            roughness=0.28,
            coat_weight=0.30
        ),
        # 7. Forged Diamond-Cut / Gunmetal Titanium Wheels
        MaterialSpec(
            name="Revuelto_Wheels_TireSidewall",
            base_color=(0.016, 0.016, 0.016, 1.0),
            metallic=0.0,
            roughness=0.82
        ),
        MaterialSpec(
            name="Revuelto_Wheels_TireTread",
            base_color=(0.018, 0.018, 0.018, 1.0),
            metallic=0.0,
            roughness=0.85
        ),
        # 8. Carbon Ceramic Drilled Brake Rotors
        MaterialSpec(
            name="Revuelto_Brakes_Rotors",
            base_color=(0.38, 0.38, 0.39, 1.0),
            metallic=0.92,
            roughness=0.18
        ),
        # 9. High-Gloss Racing Brembo Calipers (Vibrant Sport Amber / Orange)
        MaterialSpec(
            name="Revuelto_Brakes_Calipers",
            base_color=(0.95, 0.45, 0.02, 1.0),
            metallic=0.25,
            roughness=0.06,
            coat_weight=1.0,
            coat_roughness=0.02
        ),
        # 10. Crystal Headlight Polycarbonate & LED DRLs
        MaterialSpec(
            name="Revuelto_Lights_Headlights",
            base_color=(0.92, 0.95, 1.0, 0.35),
            metallic=0.10,
            roughness=0.03,
            alpha=0.35,
            emission=(0.95, 0.98, 1.0, 1.0),
            emission_strength=3.5
        ),
        # 11. 3D Crystalline Taillights (Signature Y-Pattern)
        MaterialSpec(
            name="Revuelto_Lights_Taillights",
            base_color=(0.85, 0.02, 0.02, 0.85),
            metallic=0.05,
            roughness=0.12,
            alpha=0.85,
            emission=(1.0, 0.05, 0.02, 1.0),
            emission_strength=4.0
        ),
        # 12. Interior Alcantara & Cockpit Trim
        MaterialSpec(
            name="Revuelto_Interior_Cabin",
            base_color=(0.04, 0.04, 0.045, 1.0),
            metallic=0.05,
            roughness=0.65
        ),
        # 13. Rear View Mirror Glass
        MaterialSpec(
            name="Revuelto_Mirrors_Reflective",
            base_color=(0.90, 0.92, 0.95, 1.0),
            metallic=0.98,
            roughness=0.02
        ),
        # 14. Chassis Underbody Shield
        MaterialSpec(
            name="Revuelto_Chassis_Underbody",
            base_color=(0.02, 0.02, 0.02, 1.0),
            metallic=0.40,
            roughness=0.45
        ),
    ]

    for spec in specs:
        apply_material_spec(spec)
        log_step(f"Applied luxury spec: {spec.name}")

def export_scene(out_glb: str = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\gltf\base_scene.glb") -> None:
    log_step("Exporting base_scene.glb...")
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)

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
def run() -> None:
    configure_all_luxury_materials()
    export_scene()
#endregion

#region Main
if __name__ == '__main__':
    run()
#endregion

