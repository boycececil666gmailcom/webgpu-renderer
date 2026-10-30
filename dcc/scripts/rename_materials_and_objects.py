#region Imports
import bpy
import os
#endregion

#region Scaffolding
def log(fn: str, msg: str) -> None:
    print(f"[RenameParts-{fn}] {msg}")

def rename_materials_and_objects():
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    log("rename_materials_and_objects", f"Opening {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=blend_path)

    # 1. Map of legacy car materials -> explicit part-aligned material names
    mat_rename_map = {
        "MetallicWhite.001": "Revuelto_Body_Paint",
        "MetallicBlack02.001": "Revuelto_Trim_Black",
        "Carbon.001": "Revuelto_Carbon_Fiber",
        "MetallicRed.001": "Revuelto_Accent_Red",
        "GlassWhite.001": "Revuelto_Glass_Clear",
        "GlassBlack.001": "Revuelto_Glass_Tinted",
        "Light.001": "Revuelto_Lights_Headlights",
        "LightRed.001": "Revuelto_Lights_Taillights",
        "Mirror.001": "Revuelto_Mirrors_Reflective",
        "Interior.001": "Revuelto_Interior_Cabin",
        "Logo.001": "Revuelto_Badges_Shield",
        "Logo02.001": "Revuelto_Badges_Steering",
        "BrakeDisc.001": "Revuelto_Brakes_Rotors",
        "TITANIUM - brushed.002": "Revuelto_Brakes_Calipers",
        "BottomCar.001": "Revuelto_Chassis_Underbody",
        "TireColor.001": "Revuelto_Wheels_TireTread",
        "Tire.001": "Revuelto_Wheels_TireSidewall",
    }

    log("rename_materials_and_objects", "Renaming materials...")
    for old_name, new_name in mat_rename_map.items():
        mat = bpy.data.materials.get(old_name)
        if mat:
            mat.name = new_name
            log("rename_materials_and_objects", f"  Material '{old_name}' -> '{mat.name}'")

    # 2. Map of 17 active render objects -> clean part-aligned object names
    # Matching exactly: 1 Object Name == 1 Material Name
    obj_rename_map = {
        "Revuelto_Body_Paint_White": "Revuelto_Body_Paint",
        "Revuelto_Trim_MetallicBlack": "Revuelto_Trim_Black",
        "Revuelto_Carbon_Monocoque": "Revuelto_Carbon_Fiber",
        "Revuelto_Accent_MetallicRed": "Revuelto_Accent_Red",
        "Revuelto_Glass_Clear": "Revuelto_Glass_Clear",
        "Revuelto_Glass_Tinted": "Revuelto_Glass_Tinted",
        "Revuelto_Lights_Headlights": "Revuelto_Lights_Headlights",
        "Revuelto_Lights_Taillights": "Revuelto_Lights_Taillights",
        "Revuelto_Mirrors_Reflective": "Revuelto_Mirrors_Reflective",
        "Revuelto_Interior_Cabin": "Revuelto_Interior_Cabin",
        "Revuelto_Badges_Shield": "Revuelto_Badges_Shield",
        "Revuelto_Badges_Steering": "Revuelto_Badges_Steering",
        "Revuelto_Brakes_Rotors": "Revuelto_Brakes_Rotors",
        "Revuelto_Brakes_Calipers": "Revuelto_Brakes_Calipers",
        "Revuelto_Chassis_Underbody": "Revuelto_Chassis_Underbody",
        "Revuelto_Wheels_TireTread": "Revuelto_Wheels_TireTread",
        "Revuelto_Wheels_TireSidewall": "Revuelto_Wheels_TireSidewall",
    }

    log("rename_materials_and_objects", "Renaming active render objects...")
    car_col = bpy.data.collections.get("Lamborghini_Revuelto")
    if car_col:
        for old_name, new_name in obj_rename_map.items():
            obj = bpy.data.objects.get(old_name)
            if obj:
                obj.name = new_name
                log("rename_materials_and_objects", f"  Active Object '{old_name}' -> '{obj.name}'")

    # 3. Rename remaining 21 cryptic objects in Detailed Reference collection
    ref_rename_map = {
        "Box002": "Aero_WheelArch_Liner_Bk_L",
        "Box004": "Aero_WheelArch_Liner_Bk_R",
        "Box003": "Chassis_SuspensionMount_Bk_R",
        "Object442": "Chassis_SuspensionMount_Bk_L",
        "Line001": "Trim_WheelArch_Louver_Bk_L",
        "Line004": "Trim_WheelArch_Louver_Ft_L",
        "Line009": "Trim_WheelArch_Louver_Ft_R",
        "Line006": "Chassis_FloorPan_UnderbodyShield",
        "Object038": "Grille_RadiatorCowl_Baffle",
        "Object039": "Grille_RadiatorCowl_Mesh",
        "Object042": "Aero_FrontSplitter_UnderTray",
        "Object051": "Wheel_CenterHub_Ring_Bk_L",
        "Object052": "Wheel_CenterHub_Ring_Ft_L",
        "Object054": "Wheel_CenterHub_Ring_Bk_R",
        "Object055": "Wheel_CenterHub_Ring_Ft_R",
        "Object062": "Powertrain_EngineBay_HeatShieldMesh",
        "Object430": "Aero_FrontBrakeDuct_Inlet_L",
        "Object435": "Aero_FrontBrakeDuct_Housing_L",
        "Object446": "Aero_FrontBrakeDuct_Inlet_R",
        "Object447": "Aero_FrontBrakeDuct_Housing_R",
        "Plane011": "Badge_FrontNose_EmblemMount",
    }

    log("rename_materials_and_objects", "Renaming reference subsystem objects...")
    for old_name, new_name in ref_rename_map.items():
        obj = bpy.data.objects.get(old_name)
        if obj:
            obj.name = new_name
            log("rename_materials_and_objects", f"  Ref Object '{old_name}' -> '{obj.name}'")

    # 4. Re-assign newly renamed reference objects to appropriate subsystem collections
    sub_col_moves = {
        "Wheel_CenterHub_Ring_Bk_L": ("01_Body_Exterior", "06_Wheels_Brakes"),
        "Wheel_CenterHub_Ring_Ft_L": ("01_Body_Exterior", "06_Wheels_Brakes"),
        "Wheel_CenterHub_Ring_Bk_R": ("01_Body_Exterior", "06_Wheels_Brakes"),
        "Wheel_CenterHub_Ring_Ft_R": ("01_Body_Exterior", "06_Wheels_Brakes"),
        "Aero_FrontBrakeDuct_Inlet_L": ("01_Body_Exterior", "02_Aerodynamics"),
        "Aero_FrontBrakeDuct_Housing_L": ("01_Body_Exterior", "02_Aerodynamics"),
        "Aero_FrontBrakeDuct_Inlet_R": ("01_Body_Exterior", "02_Aerodynamics"),
        "Aero_FrontBrakeDuct_Housing_R": ("01_Body_Exterior", "02_Aerodynamics"),
        "Powertrain_EngineBay_HeatShieldMesh": ("01_Body_Exterior", "04_Powertrain"),
    }

    for obj_name, (from_col_name, to_col_name) in sub_col_moves.items():
        obj = bpy.data.objects.get(obj_name)
        from_col = bpy.data.collections.get(from_col_name)
        to_col = bpy.data.collections.get(to_col_name)
        if obj and from_col and to_col:
            if obj.name in from_col.objects:
                from_col.objects.unlink(obj)
            if obj.name not in to_col.objects:
                to_col.objects.link(obj)
            log("rename_materials_and_objects", f"  Moved '{obj_name}' from {from_col_name} to {to_col_name}")

    # 5. Verify 1:1 mapping on active render collection
    log("rename_materials_and_objects", "Verifying active collection 1:1 object-to-material mapping:")
    for obj in car_col.objects:
        if obj.type == 'MESH':
            mats = [m.name for m in obj.data.materials if m]
            assert len(mats) == 1, f"Expected 1 material on {obj.name}, found {len(mats)}"
            assert obj.name == mats[0], f"Mismatch: Object '{obj.name}' has material '{mats[0]}'"
            log("rename_materials_and_objects", f"  OK: Object '{obj.name}' <==> Material '{mats[0]}'")

    # 6. Deep purge and save compressed blend
    for _ in range(4):
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    bpy.ops.wm.save_mainfile(filepath=blend_path, compress=True)
    log("rename_materials_and_objects", f"Saved compressed asset.blend ({os.path.getsize(blend_path)/(1024*1024):.2f} MB).")

    # 7. Render verification shot
    render_path = r"C:\Users\boyce\.gemini\antigravity\brain\722e3f69-5804-4a4b-b54b-ebccc9aed1a5\rendered_scene_camera.png"
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.device = 'GPU'
    cpref = bpy.context.preferences.addons['cycles'].preferences
    cpref.compute_device_type = 'OPTIX'
    for d in cpref.devices:
        if 'RTX' in d.name: d.use = True
    bpy.context.scene.cycles.samples = 32
    bpy.context.scene.render.resolution_x = 1280
    bpy.context.scene.render.resolution_y = 720
    bpy.context.scene.render.filepath = render_path
    log("rename_materials_and_objects", f"Rendering verification image to {render_path}...")
    bpy.ops.render.render(write_still=True)
    log("rename_materials_and_objects", "Verification render finished successfully!")
#endregion

#region Core
def main() -> None:
    rename_materials_and_objects()

if __name__ == "__main__":
    main()
#endregion

