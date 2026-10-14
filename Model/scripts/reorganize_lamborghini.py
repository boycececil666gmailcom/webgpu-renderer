#region ReorganizeLamborghiniModule
import bpy
from mathutils import Vector
from pathlib import Path

def log(fn: str, msg: str) -> None:
    print(f"[LamboReorg-{fn}] {msg}")

def reorganize_lamborghini_scene(blend_path: str) -> None:
    log("reorganize", f"Opening {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=blend_path)

    # 1. Map all cryptic names to explicit McLaren-style names
    name_mapping = {
        # Wheels & Tires
        "Wheel_002": "Rim_Ft_L",
        "Wheel_002.001": "Tire_Ft_L",
        "Wheel_005": "Rim_Ft_R",
        "Wheel_005.001": "Tire_Ft_R",
        "Wheel_001": "Rim_Bk_L",
        "Wheel_001.001": "Tire_Bk_L",
        "Wheel_004": "Rim_Bk_R",
        "Wheel_004.001": "Tire_Bk_R",

        # Brakes
        "Cylinder001": "BrakeDisks_Ft_L",
        "Cylinder013": "BrakeDisks_Ft_R",
        "Object438": "BrakeDisks_Bk_L",
        "Object444": "BrakeDisks_Bk_R",
        "Object003": "Brakes_Caliper_Ft_L",
        "Object004": "Brakes_Caliper_Ft_R",
        "Object005": "Brakes_Caliper_Bk_L",
        "Object006": "Brakes_Caliper_Bk_R",
        "Object007": "Brakes_Hardware_01",
        "Object009": "Brakes_Hardware_02",
        "Object010": "Brakes_Hardware_03",
        "Object011": "Brakes_Hardware_04",
        "Object012": "Brakes_Hardware_05",
        "Object044": "Brakes_Hardware_06",
        "Plane001": "Brakes_Mount_Ft",
        "Plane021": "Brakes_Mount_Bk",

        # Lighting & Glass
        "Object035": "Headlights_LED_DRL",
        "Object036": "Headlights_Lens_Glass",
        "Object040": "Headlights_Housing_Glass",
        "Object056": "Taillights_LED_Center",
        "Object059": "Taillights_LED_Left",
        "Object060": "Taillights_LED_Right",
        "Object043": "Mirrors_Glass_L",
        "Object057": "Mirrors_Glass_R",
        "Plane008": "Glass_Windshield",
        "Plane009": "Glass_EngineCover",
        "Plane020": "Glass_SideWindow_L",
        "Plane022": "Glass_SideWindow_R",
        "Plane029": "Glass_QuarterWindow",

        # Interior & Badges
        "Object047": "Interior_Dashboard_Console",
        "Object058": "Interior_SteeringWheel_Cluster",
        "Plane027": "Interior_Seats",
        "Plane028": "Interior_DoorPanels",
        "_plane27": "Interior_Floor_Upholstery",
        "Lambo_logo": "Badge_Hood_Shield",
        "Lambo_logo001": "Badge_WheelCap_Ft_L",
        "Lambo_logo006": "Badge_WheelCap_Ft_R",
        "Lambo_logo007": "Badge_WheelCap_Bk_L",
        "Lambo_logo008": "Badge_WheelCap_Bk_R",
        "Plane014": "Badge_SteeringWheel",
        "Lambo_Text": "Badge_Rear_Script_Main",
        "Lambo_Text002": "Badge_Rear_Script_TrimL",
        "Lambo_Text003": "Badge_Rear_Script_TrimR",

        # Aerodynamics
        "grill": "Grille_Front_Intake",
        "Plane003": "Spoiler_Active_Wing",
        "Plane004": "Aero_SideIntake_Scoop_L",
        "Plane007": "Aero_SideIntake_Scoop_R",
        "Plane012": "Aero_RearVent_Louver_L",
        "Plane016": "Aero_RearVent_Louver_R",
        "Plane025": "Aero_Diffuser_Underbody",

        # Powertrain
        "Cylinder002": "Exhaust_Tip_01",
        "Cylinder004": "Exhaust_Tip_02",
        "Cylinder008": "Exhaust_Tip_03",
        "Cylinder010": "Exhaust_Tip_04",
        "Cylinder003": "Exhaust_Baffle_01",
        "Cylinder005": "Exhaust_Baffle_02",
        "Cylinder009": "Exhaust_Baffle_03",
        "Cylinder011": "Exhaust_Baffle_04",
        "Cylinder012": "Exhaust_Muffler_Pipes",

        # Body Exterior (Panels, Carbon, Trim)
        "carbon": "MainCarbon_MonocoqueRoof",
        "Object434": "MainCarbon_SideSkirts",
        "Object041": "MainPaintjob_Body_Hood",
        "Object437": "MainPaintjob_Door_L",
        "Object445": "MainPaintjob_Door_R",
        "Object441": "MainPaintjob_RearFender_L",
        "Object443": "MainPaintjob_RearFender_R",
        "Line005": "MainPaintjob_Stripe_FrontL",
        "Line007": "MainPaintjob_Stripe_FrontR",
        "Line008": "MainPaintjob_Stripe_Center",
        "Object014": "MainBlack_RearBumper_Diffuser",
        "Object027": "MainBlack_FrontSplitter",
        "Plane017": "MainBlack_WindowTrim_Pillars",
        "Plane030": "MainRed_SideAccent_Stripe",
        "Object046": "MainRed_FrontSplitter_Accent",
        "Object048": "MainRed_Marker_Detail",
        "Plane015": "MainRed_RearAccent_Fin",
        "wiper002": "Wiper_Windshield",
    }

    # Rename known objects
    for old_name, new_name in name_mapping.items():
        obj = bpy.data.objects.get(old_name)
        if obj:
            obj.name = new_name

    # 2. Master Root Empty (replacing EMP_Lamborghini_Revuelto)
    root = bpy.data.objects.get("EMP_Lamborghini_Revuelto")
    if root:
        root.name = "Revuelto.Body"
    else:
        root = bpy.data.objects.get("Revuelto.Body")
        if not root:
            root = bpy.data.objects.new("Revuelto.Body", None)
            root.empty_display_type = 'ARROWS'
            root.empty_display_size = 2.0
            bpy.context.scene.collection.objects.link(root)

    # 3. Create the 4 McLaren-style Wheel Empties
    wheel_hubs = {
        "Revuelto-Wheel.Ft.L": Vector((-0.9267, 0.4220, 2.7235)),
        "Revuelto-Wheel.Ft.R": Vector((-0.9268, 0.4220, 1.0280)),
        "Revuelto-Wheel.Bk.L": Vector((-3.6917, 0.4220, 2.7006)),
        "Revuelto-Wheel.Bk.R": Vector((-3.6918, 0.4220, 1.0598)),
    }
    
    wheel_empties = {}
    for empty_name, hub_pos in wheel_hubs.items():
        emp = bpy.data.objects.get(empty_name)
        if not emp:
            emp = bpy.data.objects.new(empty_name, None)
            emp.empty_display_type = 'CIRCLE'
            emp.empty_display_size = 0.35
            bpy.context.scene.collection.objects.link(emp)
        emp.location = hub_pos
        emp.parent = root
        wheel_empties[empty_name] = emp

    # Parent Rims and Tires to respective Wheel Empties
    wheel_parenting = {
        "Rim_Ft_L": "Revuelto-Wheel.Ft.L",
        "Tire_Ft_L": "Revuelto-Wheel.Ft.L",
        "Rim_Ft_R": "Revuelto-Wheel.Ft.R",
        "Tire_Ft_R": "Revuelto-Wheel.Ft.R",
        "Rim_Bk_L": "Revuelto-Wheel.Bk.L",
        "Tire_Bk_L": "Revuelto-Wheel.Bk.L",
        "Rim_Bk_R": "Revuelto-Wheel.Bk.R",
        "Tire_Bk_R": "Revuelto-Wheel.Bk.R",
    }
    for obj_name, parent_empty_name in wheel_parenting.items():
        obj = bpy.data.objects.get(obj_name)
        parent_emp = wheel_empties.get(parent_empty_name)
        if obj and parent_emp:
            obj.parent = parent_emp

    # 4. Build Clean 6-Subsystem Collection Hierarchy
    # Master collection: Lamborghini_Revuelto
    master_col = bpy.data.collections.get("Lamborghini_Revuelto")
    if not master_col:
        master_col = bpy.data.collections.new("Lamborghini_Revuelto")
        bpy.context.scene.collection.children.link(master_col)

    sub_collection_names = [
        "01_Body_Exterior",
        "02_Aerodynamics",
        "03_Lighting_Glass",
        "04_Powertrain",
        "05_Interior",
        "06_Wheels_Brakes",
    ]

    sub_cols = {}
    for sc_name in sub_collection_names:
        sc = bpy.data.collections.get(sc_name)
        if not sc:
            sc = bpy.data.collections.new(sc_name)
        if sc.name not in master_col.children:
            try:
                master_col.children.link(sc)
            except RuntimeError:
                pass
        # Unlink from scene root if direct child
        if sc.name in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.unlink(sc)
        sub_cols[sc_name] = sc

    # Categorization mapping
    category_rules = {
        "05_Interior": ["Interior", "Steering", "Seat", "Console"],
        "03_Lighting_Glass": ["Headlight", "Taillight", "Light", "Glass", "Mirror"],
        "04_Powertrain": ["Exhaust", "Muffler", "Engine"],
        "02_Aerodynamics": ["Grille", "Spoiler", "Aero", "Diffuser", "Scoop", "Louver"],
        "06_Wheels_Brakes": ["Wheel", "Rim", "Tire", "Brake", "TITANIUM", "WheelCap"],
        "01_Body_Exterior": ["Badge", "Logo", "Main", "Body", "Carbon", "Paintjob", "Wiper", "Line", "Box", "Plane", "Object", "Cylinder"],
    }

    # Move objects to appropriate collections
    car_objects = [o for o in bpy.data.objects if o.parent == root or o == root or o in wheel_empties.values() or o.parent in wheel_empties.values()]

    for obj in car_objects:
        # Determine target collection
        assigned = False
        for cat_name, keywords in category_rules.items():
            if any(k.lower() in obj.name.lower() for k in keywords):
                target_col = sub_cols[cat_name]
                if obj.name not in target_col.objects:
                    target_col.objects.link(obj)
                assigned = True
                break
        if not assigned:
            # Default to Body Exterior
            if obj.name not in sub_cols["01_Body_Exterior"].objects:
                sub_cols["01_Body_Exterior"].objects.link(obj)

        # Unlink from other old collections
        for col in list(obj.users_collection):
            if col != sub_cols["01_Body_Exterior"] and col not in sub_cols.values():
                col.objects.unlink(obj)

    # 5. Clean up old empty collections
    old_col_names = ["02_VEHICLE", "Body_Exterior", "Glass_Lights", "Interior_Badges", "Wheels_Brakes"]
    for ocn in old_col_names:
        old_col = bpy.data.collections.get(ocn)
        if old_col and len(old_col.objects) == 0:
            bpy.data.collections.remove(old_col)
            log("reorganize", f"Removed old empty collection '{ocn}'.")

    log("reorganize", "Saving reorganized Lamborghini in the forest.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    log("reorganize", "Successfully reorganized Lamborghini model.")

def append_reorganized_lambo_to_asset_library(lambo_blend: str, asset_blend: str) -> None:
    """Appends the reorganized Lamborghini_Revuelto collection into asset.blend."""
    log("append_to_asset", f"Opening {asset_blend}")
    bpy.ops.wm.open_mainfile(filepath=asset_blend)

    log("append_to_asset", f"Linking Lamborghini_Revuelto from {lambo_blend}")
    with bpy.data.libraries.load(lambo_blend, link=False) as (data_from, data_to):
        data_to.collections = [c for c in data_from.collections if "Revuelto" in c or c.startswith("0")]
        data_to.objects = [o for o in data_from.objects if "Revuelto" in o or "Rim" in o or "Tire" in o or "Brake" in o or "Main" in o or "Interior" in o or "Glass" in o or "Headlight" in o or "Taillight" in o]

    for col in data_to.collections:
        if col and col.name == "Lamborghini_Revuelto":
            if col.name not in bpy.context.scene.collection.children:
                try:
                    bpy.context.scene.collection.children.link(col)
                except RuntimeError:
                    pass

    bpy.ops.wm.save_as_mainfile(filepath=asset_blend)
    log("append_to_asset", f"Saved updated asset library: {asset_blend}")

def main():
    base_dir = Path("c:/Users/boyce/OneDrive/Desktop/webgpu-renderer/Model")
    lambo_blend = str(base_dir / "Lamborghini in the forest.blend")
    asset_blend = str(base_dir / "asset.blend")

    reorganize_lamborghini_scene(lambo_blend)
    append_reorganized_lambo_to_asset_library(lambo_blend, asset_blend)

if __name__ == "__main__":
    main()
#endregion

