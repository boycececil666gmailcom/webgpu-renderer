#region GroupCarByMaterialModule
import bpy
from collections import defaultdict
import os
import mathutils

def log(fn: str, msg: str) -> None:
    print(f"[MaterialGroup-{fn}] {msg}")

def group_car_by_material():
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    log("group_car_by_material", f"Opening {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=blend_path)

    car_root = bpy.data.objects.get("Revuelto.Body")
    assert car_root is not None, "Revuelto.Body root empty not found"

    car_col = bpy.data.collections.get("Lamborghini_Revuelto")
    assert car_col is not None, "Lamborghini_Revuelto collection not found"

    ref_col = bpy.data.collections.get("Lamborghini_Revuelto_Detailed_Ref")
    assert ref_col is not None, "Lamborghini_Revuelto_Detailed_Ref collection not found"

    # 1. Unhide reference collection temporarily so dependency graph evaluates transforms
    ref_col.hide_viewport = False
    ref_col.hide_render = False
    bpy.context.view_layer.update()

    # 2. Clean up any existing combined objects in car_col (preserve car_root)
    for o in list(car_col.objects):
        if o != car_root:
            bpy.data.objects.remove(o, do_unlink=True)

    # 3. Gather all detailed reference meshes
    detailed_meshes = []
    def gather_meshes(c):
        for o in c.objects:
            if o.type == 'MESH' and o not in detailed_meshes:
                detailed_meshes.append(o)
        for sub in c.children:
            gather_meshes(sub)
    gather_meshes(ref_col)
    log("group_car_by_material", f"Found {len(detailed_meshes)} detailed reference meshes.")

    # 4. Duplicate meshes while preserving exact parent hierarchy
    expanded_clones = []
    for o in detailed_meshes:
        dup = o.copy()
        dup.data = o.data.copy()
        bpy.context.scene.collection.objects.link(dup)

        if len(dup.data.materials) > 1:
            log("group_car_by_material", f"Separating multi-material object: {o.name}")
            bpy.ops.object.select_all(action='DESELECT')
            dup.select_set(True)
            bpy.context.view_layer.objects.active = dup
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.separate(type='MATERIAL')
            bpy.ops.object.mode_set(mode='OBJECT')
            for sep_obj in bpy.context.selected_objects:
                expanded_clones.append(sep_obj)
        else:
            expanded_clones.append(dup)

    # 5. Group cloned pieces by material name
    mat_to_objs = defaultdict(list)
    for o in expanded_clones:
        mats = [m.name for m in o.data.materials if m]
        mat_name = mats[0] if mats else "[NO_MATERIAL]"
        mat_to_objs[mat_name].append(o)

    name_lookup = {
        "MetallicWhite.001": "Revuelto_Body_Paint_White",
        "MetallicBlack02.001": "Revuelto_Trim_MetallicBlack",
        "Carbon.001": "Revuelto_Carbon_Monocoque",
        "MetallicRed.001": "Revuelto_Accent_MetallicRed",
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

    # 6. Join per material without disturbing parent hierarchy or inverse matrices
    combined_objects = []
    for mat_name, objs in mat_to_objs.items():
        if len(objs) > 1:
            bpy.ops.object.select_all(action='DESELECT')
            for o in objs:
                o.select_set(True)
            bpy.context.view_layer.objects.active = objs[0]
            bpy.ops.object.join()
            joined = bpy.context.view_layer.objects.active
        else:
            joined = objs[0]

        # Standardize material slot: exactly 1 material assigned
        orig_mat = bpy.data.materials.get(mat_name)
        joined.data.materials.clear()
        if orig_mat:
            joined.data.materials.append(orig_mat)

        # Set descriptive engine-ready name
        joined.name = name_lookup.get(mat_name, f"Revuelto_Mat_{mat_name.replace(' ', '_').replace('.', '_')}")
        combined_objects.append(joined)
        log("group_car_by_material", f"Joined -> {joined.name} ({len(joined.data.vertices):,} verts, {len(joined.data.polygons):,} faces)")

    # 7. Move joined objects to active Lamborghini_Revuelto collection
    for o in combined_objects:
        if o.name in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.unlink(o)
        if o.name not in car_col.objects:
            car_col.objects.link(o)

    if car_root.name not in car_col.objects:
        car_col.objects.link(car_root)

    # 8. Hide reference collection from viewport and render
    ref_col.hide_viewport = True
    ref_col.hide_render = True
    bpy.context.view_layer.update()

    # Verify world coordinates of joined car
    all_corners = []
    for o in combined_objects:
        all_corners.extend([o.matrix_world @ mathutils.Vector(c) for c in o.bound_box])
    min_c = mathutils.Vector((min(c.x for c in all_corners), min(c.y for c in all_corners), min(c.z for c in all_corners)))
    max_c = mathutils.Vector((max(c.x for c in all_corners), max(c.y for c in all_corners), max(c.z for c in all_corners)))
    center = (min_c + max_c) / 2
    log("group_car_by_material", f"Verified joined car world bounding box: min={min_c}, max={max_c}, center={center}")

    # 9. Deep purge orphans and save compressed blend
    for _ in range(4):
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    bpy.ops.wm.save_mainfile(filepath=blend_path, compress=True)
    log("group_car_by_material", f"Saved compressed asset.blend ({os.path.getsize(blend_path)/(1024*1024):.2f} MB).")

    # 10. Render verification shot
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
    log("group_car_by_material", f"Rendering verification image to {render_path}...")
    bpy.ops.render.render(write_still=True)
    log("group_car_by_material", "Verification render finished successfully!")

if __name__ == "__main__":
    group_car_by_material()
#endregion
