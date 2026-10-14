#region GroundAndRoadPipelineModule
import bpy
import bmesh
import math
import os
import time
from pathlib import Path

def log(fn: str, msg: str) -> None:
    print(f"[GroundPipeline-{fn}] {msg}")

def setup_cycles_optix(scene: bpy.types.Scene) -> None:
    """Configures Cycles with OptiX GPU acceleration for ultra-fast rendering/baking."""
    scene.render.engine = 'CYCLES'
    cpref = bpy.context.preferences.addons['cycles'].preferences
    cpref.compute_device_type = 'OPTIX'
    cpref.get_devices()
    for d in cpref.devices:
        if 'RTX' in d.name:
            d.use = True
    scene.cycles.device = 'GPU'
    scene.cycles.samples = 1

def create_circular_road_mesh(name: str = "ENV_Road_Asphalt_ClosedLoop",
                              radius_center: float = 20.0,
                              width: float = 6.0,
                              num_radial: int = 128,
                              uv_repeats: float = 32.0) -> bpy.types.Object:
    """Builds a seamless closed circular road ring with realistic cross-section camber and shoulders."""
    log("create_circular_road_mesh", f"Generating circular road mesh (R={radius_center}m, W={width}m, Segments={num_radial})")
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    half_w = width / 2.0
    shoulder_w = 0.40
    # 5 profile points: inner shoulder base, inner edge, centerline crown, outer edge, outer shoulder base
    radii = [
        radius_center - half_w - shoulder_w,
        radius_center - half_w,
        radius_center,
        radius_center + half_w,
        radius_center + half_w + shoulder_w
    ]
    heights = [0.002, 0.018, 0.032, 0.018, 0.002]
    v_coords = [0.0, 0.05, 0.50, 0.95, 1.0]

    rings = []
    for i in range(num_radial):
        theta = 2.0 * math.pi * (i / num_radial)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        ring_verts = []
        for r, z in zip(radii, heights):
            v = bm.verts.new((r * cos_t, r * sin_t, z))
            ring_verts.append(v)
        rings.append(ring_verts)

    bm.verts.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.verify()

    for i in range(num_radial):
        next_i = (i + 1) % num_radial
        u_curr = (i / num_radial) * uv_repeats
        u_next = ((i + 1) / num_radial) * uv_repeats

        for j in range(4):
            v0 = rings[i][j]
            v1 = rings[next_i][j]
            v2 = rings[next_i][j+1]
            v3 = rings[i][j+1]

            face = bm.faces.new((v0, v1, v2, v3))
            for loop in face.loops:
                if loop.vert == v0:
                    loop[uv_layer].uv = (u_curr, v_coords[j])
                elif loop.vert == v1:
                    loop[uv_layer].uv = (u_next, v_coords[j])
                elif loop.vert == v2:
                    loop[uv_layer].uv = (u_next, v_coords[j+1])
                elif loop.vert == v3:
                    loop[uv_layer].uv = (u_curr, v_coords[j+1])

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    log("create_circular_road_mesh", f"Created {name}: {len(mesh.vertices)} verts, {len(mesh.polygons)} quads.")
    return obj

def create_terrain_mesh(name: str = "ENV_Terrain_Forest_Floor_Layered",
                        size: float = 60.0,
                        subdivisions: int = 32) -> bpy.types.Object:
    """Builds a clean subdivided 60m x 60m terrain plane with [0, 1] UVs."""
    log("create_terrain_mesh", f"Generating terrain mesh ({size}m x {size}m, {subdivisions}x{subdivisions} quads)")
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    half_s = size / 2.0
    bmesh.ops.create_grid(bm, x_segments=subdivisions, y_segments=subdivisions, size=half_s)
    uv_layer = bm.loops.layers.uv.verify()

    for f in bm.faces:
        for l in f.loops:
            l[uv_layer].uv = (l.vert.co.x / size + 0.5, l.vert.co.y / size + 0.5)

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    log("create_terrain_mesh", f"Created {name}: {len(mesh.vertices)} verts, {len(mesh.polygons)} quads.")
    return obj

def bake_layered_ground_textures(textures_dir: str) -> tuple[str, str, str]:
    """Bakes multi-layer non-repetitive forest floor PBR maps using an isolated OptiX bake scene."""
    log("bake_layered_ground_textures", "Starting multi-layer ground texture bake (4096 x 4096)...")
    os.makedirs(textures_dir, exist_ok=True)

    alb_path = os.path.join(textures_dir, "Forest_Floor_Layered_Albedo.png")
    rgh_path = os.path.join(textures_dir, "Forest_Floor_Layered_Roughness.png")
    nrm_path = os.path.join(textures_dir, "Forest_Floor_Layered_Normal.png")

    # If already baked and valid on disk, skip redundant bake
    if os.path.exists(alb_path) and os.path.exists(rgh_path) and os.path.exists(nrm_path):
        log("bake_layered_ground_textures", "Cached baked 4K textures exist on disk, reusing.")
        return alb_path, rgh_path, nrm_path

    # Create isolated bake scene
    bake_scene = bpy.data.scenes.new('GroundBakeScene')
    orig_scene = bpy.context.scene
    bpy.context.window.scene = bake_scene
    setup_cycles_optix(bake_scene)

    # Isolated 60m plane
    mesh = bpy.data.meshes.new('BakeMesh_Plane')
    obj = bpy.data.objects.new('BakeObj_Plane', mesh)
    bake_scene.collection.objects.link(obj)

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=30.0)
    uv_layer = bm.loops.layers.uv.verify()
    for f in bm.faces:
        for l in f.loops:
            l[uv_layer].uv = (l.vert.co.x / 60.0 + 0.5, l.vert.co.y / 60.0 + 0.5)
    bm.to_mesh(mesh)
    bm.free()

    # Retrieve packed source textures
    soil_alb = bpy.data.images['vl4led3lw_4K_Albedo.jpg']
    soil_rgh = bpy.data.images['vl4led3lw_4K_Roughness.jpg']
    soil_nrm = bpy.data.images['vl4led3lw_4K_Normal.jpg']
    deb_alb  = bpy.data.images['Micro_Details_122']
    deb_rgh  = bpy.data.images['Micro_Details_127']
    deb_nrm  = bpy.data.images['Micro_Details_125']
    deb_alp  = bpy.data.images['Micro_Details_126']

    # Build layered node graph
    mat = bpy.data.materials.new(name="MAT_Ground_Layered_Bake")
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    tex_coord = nodes.new('ShaderNodeTexCoord')

    # Soil 1 (18x)
    map_soil_1 = nodes.new('ShaderNodeMapping')
    map_soil_1.inputs['Scale'].default_value = (18.0, 18.0, 1.0)
    links.new(tex_coord.outputs['UV'], map_soil_1.inputs['Vector'])

    tex_soil_alb_1 = nodes.new('ShaderNodeTexImage')
    tex_soil_alb_1.image = soil_alb
    links.new(map_soil_1.outputs['Vector'], tex_soil_alb_1.inputs['Vector'])

    tex_soil_rgh_1 = nodes.new('ShaderNodeTexImage')
    tex_soil_rgh_1.image = soil_rgh
    links.new(map_soil_1.outputs['Vector'], tex_soil_rgh_1.inputs['Vector'])

    tex_soil_nrm_1 = nodes.new('ShaderNodeTexImage')
    tex_soil_nrm_1.image = soil_nrm
    links.new(map_soil_1.outputs['Vector'], tex_soil_nrm_1.inputs['Vector'])

    # Soil 2 (12.3x rotated 45 deg + offset)
    map_soil_2 = nodes.new('ShaderNodeMapping')
    map_soil_2.inputs['Location'].default_value = (0.37, 0.58, 0.0)
    map_soil_2.inputs['Rotation'].default_value = (0.0, 0.0, 0.785)
    map_soil_2.inputs['Scale'].default_value = (12.3, 12.3, 1.0)
    links.new(tex_coord.outputs['UV'], map_soil_2.inputs['Vector'])

    tex_soil_alb_2 = nodes.new('ShaderNodeTexImage')
    tex_soil_alb_2.image = soil_alb
    links.new(map_soil_2.outputs['Vector'], tex_soil_alb_2.inputs['Vector'])

    tex_soil_rgh_2 = nodes.new('ShaderNodeTexImage')
    tex_soil_rgh_2.image = soil_rgh
    links.new(map_soil_2.outputs['Vector'], tex_soil_rgh_2.inputs['Vector'])

    tex_soil_nrm_2 = nodes.new('ShaderNodeTexImage')
    tex_soil_nrm_2.image = soil_nrm
    links.new(map_soil_2.outputs['Vector'], tex_soil_nrm_2.inputs['Vector'])

    # Soil mix noise
    noise_soil_mix = nodes.new('ShaderNodeTexNoise')
    noise_soil_mix.inputs['Scale'].default_value = 5.0
    noise_soil_mix.inputs['Detail'].default_value = 4.0
    links.new(tex_coord.outputs['UV'], noise_soil_mix.inputs['Vector'])

    ramp_soil_mix = nodes.new('ShaderNodeValToRGB')
    ramp_soil_mix.color_ramp.elements[0].position = 0.35
    ramp_soil_mix.color_ramp.elements[1].position = 0.65
    links.new(noise_soil_mix.outputs['Fac'], ramp_soil_mix.inputs['Fac'])

    mix_soil_alb = nodes.new('ShaderNodeMix')
    mix_soil_alb.data_type = 'RGBA'
    links.new(ramp_soil_mix.outputs['Color'], mix_soil_alb.inputs['Factor'])
    links.new(tex_soil_alb_1.outputs['Color'], mix_soil_alb.inputs['A'])
    links.new(tex_soil_alb_2.outputs['Color'], mix_soil_alb.inputs['B'])

    mix_soil_rgh = nodes.new('ShaderNodeMix')
    mix_soil_rgh.data_type = 'RGBA'
    links.new(ramp_soil_mix.outputs['Color'], mix_soil_rgh.inputs['Factor'])
    links.new(tex_soil_rgh_1.outputs['Color'], mix_soil_rgh.inputs['A'])
    links.new(tex_soil_rgh_2.outputs['Color'], mix_soil_rgh.inputs['B'])

    mix_soil_nrm = nodes.new('ShaderNodeMix')
    mix_soil_nrm.data_type = 'RGBA'
    links.new(ramp_soil_mix.outputs['Color'], mix_soil_nrm.inputs['Factor'])
    links.new(tex_soil_nrm_1.outputs['Color'], mix_soil_nrm.inputs['A'])
    links.new(tex_soil_nrm_2.outputs['Color'], mix_soil_nrm.inputs['B'])

    # Macro Tonal Noise (Damp vs Dry soil)
    macro_noise = nodes.new('ShaderNodeTexNoise')
    macro_noise.inputs['Scale'].default_value = 0.6
    macro_noise.inputs['Detail'].default_value = 3.0
    links.new(tex_coord.outputs['UV'], macro_noise.inputs['Vector'])

    macro_ramp = nodes.new('ShaderNodeValToRGB')
    macro_ramp.color_ramp.elements[0].color = (0.76, 0.73, 0.68, 1.0)
    macro_ramp.color_ramp.elements[1].color = (1.18, 1.10, 1.02, 1.0)
    links.new(macro_noise.outputs['Fac'], macro_ramp.inputs['Fac'])

    macro_mult = nodes.new('ShaderNodeMix')
    macro_mult.data_type = 'RGBA'
    macro_mult.blend_type = 'MULTIPLY'
    macro_mult.inputs['Factor'].default_value = 1.0
    links.new(mix_soil_alb.outputs['Result'], macro_mult.inputs['A'])
    links.new(macro_ramp.outputs['Color'], macro_mult.inputs['B'])

    macro_rgh_mult = nodes.new('ShaderNodeMix')
    macro_rgh_mult.data_type = 'RGBA'
    macro_rgh_mult.blend_type = 'MULTIPLY'
    macro_rgh_mult.inputs['Factor'].default_value = 0.5
    links.new(mix_soil_rgh.outputs['Result'], macro_rgh_mult.inputs['A'])
    links.new(macro_ramp.outputs['Color'], macro_rgh_mult.inputs['B'])

    # Debris (Leaves / Twigs)
    map_debris = nodes.new('ShaderNodeMapping')
    map_debris.inputs['Scale'].default_value = (11.0, 11.0, 1.0)
    links.new(tex_coord.outputs['UV'], map_debris.inputs['Vector'])

    tex_deb_alb = nodes.new('ShaderNodeTexImage')
    tex_deb_alb.image = deb_alb
    links.new(map_debris.outputs['Vector'], tex_deb_alb.inputs['Vector'])

    tex_deb_alp = nodes.new('ShaderNodeTexImage')
    tex_deb_alp.image = deb_alp
    links.new(map_debris.outputs['Vector'], tex_deb_alp.inputs['Vector'])

    tex_deb_rgh = nodes.new('ShaderNodeTexImage')
    tex_deb_rgh.image = deb_rgh
    links.new(map_debris.outputs['Vector'], tex_deb_rgh.inputs['Vector'])

    tex_deb_nrm = nodes.new('ShaderNodeTexImage')
    tex_deb_nrm.image = deb_nrm
    links.new(map_debris.outputs['Vector'], tex_deb_nrm.inputs['Vector'])

    voronoi_deb = nodes.new('ShaderNodeTexVoronoi')
    voronoi_deb.inputs['Scale'].default_value = 2.2
    links.new(tex_coord.outputs['UV'], voronoi_deb.inputs['Vector'])

    voronoi_ramp = nodes.new('ShaderNodeValToRGB')
    voronoi_ramp.color_ramp.elements[0].position = 0.28
    voronoi_ramp.color_ramp.elements[1].position = 0.52
    links.new(voronoi_deb.outputs['Distance'], voronoi_ramp.inputs['Fac'])

    deb_mask_mult = nodes.new('ShaderNodeMix')
    deb_mask_mult.data_type = 'FLOAT'
    deb_mask_mult.blend_type = 'MULTIPLY'
    deb_mask_mult.inputs['Factor'].default_value = 1.0
    links.new(voronoi_ramp.outputs['Color'], deb_mask_mult.inputs['A'])
    links.new(tex_deb_alp.outputs['Color'], deb_mask_mult.inputs['B'])

    # Composites
    final_alb = nodes.new('ShaderNodeMix')
    final_alb.data_type = 'RGBA'
    links.new(deb_mask_mult.outputs['Result'], final_alb.inputs['Factor'])
    links.new(macro_mult.outputs['Result'], final_alb.inputs['A'])
    links.new(tex_deb_alb.outputs['Color'], final_alb.inputs['B'])

    final_rgh = nodes.new('ShaderNodeMix')
    final_rgh.data_type = 'RGBA'
    links.new(deb_mask_mult.outputs['Result'], final_rgh.inputs['Factor'])
    links.new(macro_rgh_mult.outputs['Result'], final_rgh.inputs['A'])
    links.new(tex_deb_rgh.outputs['Color'], final_rgh.inputs['B'])

    final_nrm = nodes.new('ShaderNodeMix')
    final_nrm.data_type = 'RGBA'
    links.new(deb_mask_mult.outputs['Result'], final_nrm.inputs['Factor'])
    links.new(mix_soil_nrm.outputs['Result'], final_nrm.inputs['A'])
    links.new(tex_deb_nrm.outputs['Color'], final_nrm.inputs['B'])

    out_node = nodes.new('ShaderNodeOutputMaterial')
    emit_node = nodes.new('ShaderNodeEmission')
    links.new(emit_node.outputs['Emission'], out_node.inputs['Surface'])

    obj.data.materials.append(mat)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    bake_tex_node = nodes.new('ShaderNodeTexImage')
    nodes.active = bake_tex_node

    # Bake Albedo
    t0 = time.time()
    alb_img = bpy.data.images.new(name="Forest_Floor_Layered_Albedo", width=4096, height=4096)
    bake_tex_node.image = alb_img
    links.new(final_alb.outputs['Result'], emit_node.inputs['Color'])
    bpy.ops.object.bake(type='EMIT')
    alb_img.filepath_raw = alb_path
    alb_img.file_format = 'PNG'
    alb_img.save()
    log("bake_layered_ground_textures", f"Baked 4K Albedo in {time.time()-t0:.2f}s -> {alb_path}")

    # Bake Roughness
    t0 = time.time()
    rgh_img = bpy.data.images.new(name="Forest_Floor_Layered_Roughness", width=4096, height=4096)
    rgh_img.colorspace_settings.name = 'Non-Color'
    bake_tex_node.image = rgh_img
    links.new(final_rgh.outputs['Result'], emit_node.inputs['Color'])
    bpy.ops.object.bake(type='EMIT')
    rgh_img.filepath_raw = rgh_path
    rgh_img.file_format = 'PNG'
    rgh_img.save()
    log("bake_layered_ground_textures", f"Baked 4K Roughness in {time.time()-t0:.2f}s -> {rgh_path}")

    # Bake Normal
    t0 = time.time()
    nrm_img = bpy.data.images.new(name="Forest_Floor_Layered_Normal", width=4096, height=4096)
    nrm_img.colorspace_settings.name = 'Non-Color'
    bake_tex_node.image = nrm_img
    links.new(final_nrm.outputs['Result'], emit_node.inputs['Color'])
    bpy.ops.object.bake(type='EMIT')
    nrm_img.filepath_raw = nrm_path
    nrm_img.file_format = 'PNG'
    nrm_img.save()
    log("bake_layered_ground_textures", f"Baked 4K Normal in {time.time()-t0:.2f}s -> {nrm_path}")

    # Cleanup bake scene
    bpy.context.window.scene = orig_scene
    bpy.data.scenes.remove(bake_scene)

    return alb_path, rgh_path, nrm_path

def build_gltf_pbr_ground_mat(alb_path: str, rgh_path: str, nrm_path: str) -> bpy.types.Material:
    """Builds clean, standard glTF 2.0 PBR material for the layered forest floor."""
    mat_name = "MAT_ENV_Forest_Floor_Layered_glTF"
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

    # Load images
    img_alb = bpy.data.images.load(alb_path, check_existing=True)
    img_rgh = bpy.data.images.load(rgh_path, check_existing=True)
    img_rgh.colorspace_settings.name = 'Non-Color'
    img_nrm = bpy.data.images.load(nrm_path, check_existing=True)
    img_nrm.colorspace_settings.name = 'Non-Color'

    # Albedo
    tex_alb = nodes.new("ShaderNodeTexImage")
    tex_alb.location = (-400, 200)
    tex_alb.image = img_alb
    links.new(tex_alb.outputs["Color"], bsdf.inputs["Base Color"])

    # Roughness
    tex_rgh = nodes.new("ShaderNodeTexImage")
    tex_rgh.location = (-400, 0)
    tex_rgh.image = img_rgh
    links.new(tex_rgh.outputs["Color"], bsdf.inputs["Roughness"])

    # Normal Map
    norm_node = nodes.new("ShaderNodeNormalMap")
    norm_node.location = (-200, -250)
    norm_node.inputs["Strength"].default_value = 1.0
    links.new(norm_node.outputs["Normal"], bsdf.inputs["Normal"])

    tex_nrm = nodes.new("ShaderNodeTexImage")
    tex_nrm.location = (-500, -250)
    tex_nrm.image = img_nrm
    links.new(tex_nrm.outputs["Color"], norm_node.inputs["Color"])

    log("build_gltf_pbr_ground_mat", f"Created clean glTF PBR material {mat_name}.")
    return mat

def execute_pipeline():
    blend_path = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\asset.blend"
    textures_dir = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\textures"
    log("execute_pipeline", f"Opening {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=blend_path)

    # 1. Bake 4K layered ground textures
    alb_path, rgh_path, nrm_path = bake_layered_ground_textures(textures_dir)

    # 2. Reference Preservation: Rename old linear road and uniform ground
    ground_col = bpy.data.collections.get("04_Ground_Surfaces")
    assert ground_col is not None, "Collection '04_Ground_Surfaces' missing"

    old_road = bpy.data.objects.get("ENV_Road_Asphalt")
    if old_road:
        old_road.name = "ENV_Road_Asphalt_Linear_Ref"
        old_road.hide_viewport = True
        old_road.hide_render = True
        log("execute_pipeline", f"Preserved old road as {old_road.name} (hidden for reference).")

    old_terrain = bpy.data.objects.get("ENV_Terrain_Forest_Floor")
    if old_terrain:
        old_terrain.name = "ENV_Terrain_Forest_Floor_Uniform_Ref"
        old_terrain.hide_viewport = True
        old_terrain.hide_render = True
        log("execute_pipeline", f"Preserved old terrain as {old_terrain.name} (hidden for reference).")

    # 3. Create new circular road mesh
    # Center radius 20m, width 6m (inner 17m, outer 23m)
    road_mat = bpy.data.materials.get("MAT_ENV_Road_Asphalt_glTF")
    assert road_mat is not None, "Material MAT_ENV_Road_Asphalt_glTF missing"

    # Remove any prior instance if re-running
    existing_loop = bpy.data.objects.get("ENV_Road_Asphalt_ClosedLoop")
    if existing_loop:
        bpy.data.objects.remove(existing_loop, do_unlink=True)

    new_road = create_circular_road_mesh(name="ENV_Road_Asphalt_ClosedLoop",
                                         radius_center=20.0,
                                         width=6.0,
                                         num_radial=128,
                                         uv_repeats=32.0)
    new_road.data.materials.append(road_mat)
    ground_col.objects.link(new_road)
    log("execute_pipeline", f"Linked {new_road.name} with {road_mat.name} into {ground_col.name}.")

    # 4. Create new layered terrain mesh with baked glTF material
    existing_terrain = bpy.data.objects.get("ENV_Terrain_Forest_Floor_Layered")
    if existing_terrain:
        bpy.data.objects.remove(existing_terrain, do_unlink=True)

    new_terrain = create_terrain_mesh(name="ENV_Terrain_Forest_Floor_Layered",
                                      size=60.0,
                                      subdivisions=32)
    terrain_mat = build_gltf_pbr_ground_mat(alb_path, rgh_path, nrm_path)
    new_terrain.data.materials.append(terrain_mat)
    ground_col.objects.link(new_terrain)
    log("execute_pipeline", f"Linked {new_terrain.name} with {terrain_mat.name} into {ground_col.name}.")

    # 5. Position Lamborghini Revuelto onto the circular track matching user sketch
    # In sketch: car is on the left side of track driving counter-clockwise (towards +Y)
    car_root = bpy.data.objects.get("Revuelto.Body")
    if car_root:
        car_root.location = (-20.0, 0.0, 0.032) # On centerline crown
        car_root.rotation_euler = (0.0, 0.0, 0.0) # Tangent heading +Y
        log("execute_pipeline", f"Positioned {car_root.name} onto circular track at {car_root.location}.")

    # 6. Setup Camera matching user sketch
    cam = bpy.data.objects.get("CAM_Long_Road_Telephoto_50mm")
    if not cam:
        cam = bpy.data.objects.get("Camera")
    if not cam:
        cam_data = bpy.data.cameras.new("CAM_Track_Follow")
        cam = bpy.data.objects.new("CAM_Track_Follow", cam_data)
        bpy.context.scene.collection.objects.link(cam)

    cam.name = "CAM_Scene_Follow"
    # User sketch: camera at bottom-left looking up-right towards car and center island
    cam.location = (-28.0, -18.0, 3.8)
    cam.rotation_euler = (math.radians(78.0), 0.0, math.radians(-32.0))
    cam.data.lens = 45.0
    cam.data.clip_end = 200.0
    bpy.context.scene.camera = cam
    log("execute_pipeline", f"Positioned camera {cam.name} at {cam.location}.")

    # 7. Pack all textures into asset.blend
    bpy.ops.file.pack_all()
    log("execute_pipeline", "All textures packed into blend file.")

    # 8. Save updated blend file
    bpy.ops.wm.save_mainfile(filepath=blend_path)
    log("execute_pipeline", f"Saved successfully to {blend_path}")

    # 9. Render verification preview
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
    log("execute_pipeline", f"Rendering verification image to {render_path}...")
    bpy.ops.render.render(write_still=True)
    log("execute_pipeline", "Verification render completed!")

if __name__ == "__main__":
    execute_pipeline()
#endregion

