#region FixPowertrainAndWheelsModule
import bpy
import os

def log(fn: str, msg: str) -> None:
    print(f"[CarReorg-{fn}] {msg}")

def fix_powertrain_and_wheel_organization():
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    log("fix_powertrain_and_wheel_organization", f"Opening {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=blend_path)

    col_power = bpy.data.collections.get("04_Powertrain")
    col_wheels = bpy.data.collections.get("06_Wheels_Brakes")
    col_body = bpy.data.collections.get("01_Body_Exterior")
    col_interior = bpy.data.collections.get("05_Interior")

    assert col_power and col_wheels and col_body and col_interior, "Required collections missing"

    # 1. Map misnamed wheel rim spokes (was Exhaust_Tip_01..04)
    # Positions relative to car body:
    # Exhaust_Tip_01: (0.7936,  0.5929, 0.2511) -> Back Left Rim Spokes
    # Exhaust_Tip_02: (-0.8513, 0.6066, 0.2511) -> Front Left Rim Spokes
    # Exhaust_Tip_03: (0.7935, -0.5608, 0.2511) -> Back Right Rim Spokes
    # Exhaust_Tip_04: (-0.8514, -0.5797, 0.2511) -> Front Right Rim Spokes
    spoke_mapping = {
        "Exhaust_Tip_01": "Wheel_RimSpokes_Bk_L",
        "Exhaust_Tip_02": "Wheel_RimSpokes_Ft_L",
        "Exhaust_Tip_03": "Wheel_RimSpokes_Bk_R",
        "Exhaust_Tip_04": "Wheel_RimSpokes_Ft_R",
    }
    for old_name, new_name in spoke_mapping.items():
        obj = bpy.data.objects.get(old_name)
        if obj:
            obj.name = new_name
            # Move from 04_Powertrain to 06_Wheels_Brakes
            if col_power in obj.users_collection:
                col_power.objects.unlink(obj)
            if col_wheels not in obj.users_collection:
                col_wheels.objects.link(obj)
            log("fix_powertrain_and_wheel_organization", f"Moved & renamed {old_name} -> {new_name} to 06_Wheels_Brakes")

    # 2. Map misnamed wheel lug nuts / center caps (was Exhaust_Baffle_01..04)
    # Exhaust_Baffle_01: Back Left Lug Nuts
    # Exhaust_Baffle_02: Front Left Lug Nuts
    # Exhaust_Baffle_03: Back Right Lug Nuts
    # Exhaust_Baffle_04: Front Right Lug Nuts
    baffle_mapping = {
        "Exhaust_Baffle_01": "Wheel_LugNuts_Bk_L",
        "Exhaust_Baffle_02": "Wheel_LugNuts_Ft_L",
        "Exhaust_Baffle_03": "Wheel_LugNuts_Bk_R",
        "Exhaust_Baffle_04": "Wheel_LugNuts_Ft_R",
    }
    for old_name, new_name in baffle_mapping.items():
        obj = bpy.data.objects.get(old_name)
        if obj:
            obj.name = new_name
            # Move from 04_Powertrain to 06_Wheels_Brakes
            if col_power in obj.users_collection:
                col_power.objects.unlink(obj)
            if col_wheels not in obj.users_collection:
                col_wheels.objects.link(obj)
            log("fix_powertrain_and_wheel_organization", f"Moved & renamed {old_name} -> {new_name} to 06_Wheels_Brakes")

    # 3. Clean up McLaren-style naming for tires in 06_Wheels_Brakes
    tire_mapping = {
        "Rim_Ft_L": "Wheel_TireTread_Ft_L",
        "Rim_Ft_R": "Wheel_TireTread_Ft_R",
        "Rim_Bk_L": "Wheel_TireTread_Bk_L",
        "Rim_Bk_R": "Wheel_TireTread_Bk_R",
        "Tire_Ft_L": "Wheel_TireSidewall_Ft_L",
        "Tire_Ft_R": "Wheel_TireSidewall_Ft_R",
        "Tire_Bk_L": "Wheel_TireSidewall_Bk_L",
        "Tire_Bk_R": "Wheel_TireSidewall_Bk_R",
    }
    for old_name, new_name in tire_mapping.items():
        obj = bpy.data.objects.get(old_name)
        if obj:
            obj.name = new_name
            log("fix_powertrain_and_wheel_organization", f"Renamed {old_name} -> {new_name}")

    # 4. Move miscategorized steering wheel objects to 05_Interior
    for sw_name in ["Interior_SteeringWheel_Cluster", "Badge_SteeringWheel"]:
        obj = bpy.data.objects.get(sw_name)
        if obj:
            if col_wheels in obj.users_collection:
                col_wheels.objects.unlink(obj)
            if col_interior not in obj.users_collection:
                col_interior.objects.link(obj)
            log("fix_powertrain_and_wheel_organization", f"Moved {sw_name} from wheels to 05_Interior")

    # 5. Move miscategorized trim objects to 01_Body_Exterior
    for trim_name in ["MainBlack_WindowTrim_Pillars", "Badge_Rear_Script_TrimL", "Badge_Rear_Script_TrimR"]:
        obj = bpy.data.objects.get(trim_name)
        if obj:
            if col_wheels in obj.users_collection:
                col_wheels.objects.unlink(obj)
            if col_body not in obj.users_collection:
                col_body.objects.link(obj)
            log("fix_powertrain_and_wheel_organization", f"Moved {trim_name} from wheels to 01_Body_Exterior")

    # 6. Add real exhaust tailpipe bezel (Object049) to 04_Powertrain
    obj_bezel = bpy.data.objects.get("Object049")
    if obj_bezel:
        obj_bezel.name = "Exhaust_Tailpipe_Bezel"
        if col_body in obj_bezel.users_collection:
            col_body.objects.unlink(obj_bezel)
        if col_power not in obj_bezel.users_collection:
            col_power.objects.link(obj_bezel)
        log("fix_powertrain_and_wheel_organization", f"Moved Object049 -> Exhaust_Tailpipe_Bezel to 04_Powertrain")

    # 7. Print summary of 04_Powertrain and 06_Wheels_Brakes
    log("fix_powertrain_and_wheel_organization", f"=== Updated 04_Powertrain ({len(col_power.objects)} objects) ===")
    for o in col_power.objects:
        log("fix_powertrain_and_wheel_organization", f"  {o.name}")

    log("fix_powertrain_and_wheel_organization", f"=== Updated 06_Wheels_Brakes ({len(col_wheels.objects)} objects) ===")
    for o in sorted(col_wheels.objects, key=lambda x: x.name):
        log("fix_powertrain_and_wheel_organization", f"  {o.name}")

    # 8. Save compressed
    bpy.ops.wm.save_mainfile(filepath=blend_path, compress=True)
    log("fix_powertrain_and_wheel_organization", f"Successfully saved updated {blend_path}")

if __name__ == "__main__":
    fix_powertrain_and_wheel_organization()
#endregion

