#region Imports
import bpy
import bmesh
import mathutils
import random
import numpy as np
#endregion

#region FoliageLODPipeline
def generate_foliage_lod(
    src_obj: bpy.types.Object,
    leaf_mat_idx: int,
    cull_redundant_petiole: bool,
    branch_island_ratio: float,
    branch_decimate_ratio: float,
    target_leaf_count: int,
    leaf_size_boost: float = 1.85,
    name_suffix: str = "LOD1"
) -> bpy.types.Mesh:
    """
    Generates an aggressively optimized foliage LOD mesh by:
    1. Segmenting multi-vertex leaf clusters into connected islands.
    2. Fitting planar quad cards via Principal Component Analysis (PCA) with area compensation & expanded size boost.
    3. Segmenting branch geometry into independent tubular islands and culling internal micro-twigs by volume.
    4. Decimating remaining structural branches via QEM collapse with vertex group masking.
    """
    print(f"[Foliage-LOD] Processing {src_obj.name} -> {name_suffix} (Target leaves: {target_leaf_count}, Size boost: {leaf_size_boost}x)")
    
    bm = bmesh.new()
    bm.from_mesh(src_obj.data)
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.verify()
    
    if isinstance(leaf_mat_idx, (list, tuple, set)):
        leaf_mat_indices = set(leaf_mat_idx)
    else:
        leaf_mat_indices = {leaf_mat_idx}

    # 1. Separate leaf faces from branch/trunk geometry
    leaf_faces = [f for f in bm.faces if f.material_index in leaf_mat_indices]
    if cull_redundant_petiole:
        branch_faces = [f for f in bm.faces if f.material_index == 0]
    else:
        branch_faces = [f for f in bm.faces if f.material_index not in leaf_mat_indices]
        
    # 2. Island segmentation for leaves
    visited = set()
    leaf_islands = []
    for f in leaf_faces:
        if f in visited:
            continue
        isl = []
        q = [f]
        visited.add(f)
        while q:
            curr = q.pop()
            isl.append(curr)
            for e in curr.edges:
                for linked in e.link_faces:
                    if linked not in visited and linked.material_index in leaf_mat_indices:
                        visited.add(linked)
                        q.append(linked)
        leaf_islands.append(isl)
        
    # 3. Leaf card selection and PCA fitting
    if len(leaf_islands) > target_leaf_count:
        random.seed(42 + target_leaf_count)
        surviving_islands = set(random.sample(range(len(leaf_islands)), target_leaf_count))
        base_scale = min((len(leaf_islands) / target_leaf_count) ** 0.5, 3.0)
    else:
        surviving_islands = set(range(len(leaf_islands)))
        base_scale = 1.0

    # Apply foliage enlargement multiplier
    scale_factor = base_scale * leaf_size_boost
    quad_cards_data = []

    for idx in surviving_islands:
        isl = leaf_islands[idx]
        verts = list({v for f in isl for v in f.verts})
        if len(verts) < 3:
            continue
            
        c = sum((v.co for v in verts), mathutils.Vector()) / len(verts)
        coords = np.array([[v.co.x - c.x, v.co.y - c.y, v.co.z - c.z] for v in verts])
        cov = np.cov(coords, rowvar=False)
        eig_vals, eig_vecs = np.linalg.eigh(cov)
        s_idx = np.argsort(eig_vals)[::-1]
        
        u = mathutils.Vector(eig_vecs[:, s_idx[0]]).normalized()
        v = mathutils.Vector(eig_vecs[:, s_idx[1]]).normalized()
        
        pu = [pt.dot(u) * scale_factor for pt in coords]
        pv = [pt.dot(v) * scale_factor for pt in coords]
        min_u, max_u = min(pu), max(pu)
        min_v, max_v = min(pv), max(pv)
        
        isl_uvs = [loop[uv_layer].uv for f in isl for loop in f.loops]
        if isl_uvs:
            uv_min_x, uv_max_x = min(u_val.x for u_val in isl_uvs), max(u_val.x for u_val in isl_uvs)
            uv_min_y, uv_max_y = min(u_val.y for u_val in isl_uvs), max(u_val.y for u_val in isl_uvs)
        else:
            uv_min_x, uv_max_x, uv_min_y, uv_max_y = 0.0, 1.0, 0.0, 1.0
            
        card_positions = [
            c + u * min_u + v * min_v,
            c + u * max_u + v * min_v,
            c + u * max_u + v * max_v,
            c + u * min_u + v * max_v
        ]
        card_uvs = [
            (uv_min_x, uv_min_y),
            (uv_max_x, uv_min_y),
            (uv_max_x, uv_max_y),
            (uv_min_x, uv_max_y)
        ]
        quad_cards_data.append((card_positions, card_uvs, isl[0].material_index))

    # 4. Branch island segmentation & volume sorting
    visited_b = set()
    branch_islands = []
    for f in branch_faces:
        if f in visited_b:
            continue
        isl = []
        q = [f]
        visited_b.add(f)
        while q:
            curr = q.pop()
            isl.append(curr)
            for e in curr.edges:
                for linked in e.link_faces:
                    is_valid_branch = (linked.material_index == 0) if cull_redundant_petiole else (linked.material_index not in leaf_mat_indices)
                    if linked not in visited_b and is_valid_branch:
                        visited_b.add(linked)
                        q.append(linked)
        branch_islands.append(isl)

    def island_volume(faces):
        coords = [v.co for f in faces for v in f.verts]
        if not coords:
            return 0
        min_x, max_x = min(c.x for c in coords), max(c.x for c in coords)
        min_y, max_y = min(c.y for c in coords), max(c.y for c in coords)
        min_z, max_z = min(c.z for c in coords), max(c.z for c in coords)
        dx, dy, dz = max_x - min_x, max_y - min_y, max_z - min_z
        return dx * dy * dz + (dx + dy + dz) * 0.01

    branch_islands.sort(key=island_volume, reverse=True)
    keep_branches_count = max(1, int(len(branch_islands) * branch_island_ratio))
    kept_branch_faces = [f for isl in branch_islands[:keep_branches_count] for f in isl]

    # 5. Reconstruct clean BMesh
    bm_out = bmesh.new()
    uv_out = bm_out.loops.layers.uv.verify()
    
    vmap = {}
    for f in kept_branch_faces:
        new_vs = []
        for v in f.verts:
            if v not in vmap:
                vmap[v] = bm_out.verts.new(v.co)
            new_vs.append(vmap[v])
        nf = bm_out.faces.new(new_vs)
        nf.material_index = f.material_index
        for loop, old_loop in zip(nf.loops, f.loops):
            loop[uv_out].uv = old_loop[uv_layer].uv

    for q_pos, q_uvs, q_mat_idx in quad_cards_data:
        qvs = [bm_out.verts.new(p) for p in q_pos]
        qf = bm_out.faces.new(qvs)
        qf.material_index = q_mat_idx
        for loop, uv in zip(qf.loops, q_uvs):
            loop[uv_out].uv = uv

    out_mesh = src_obj.data.copy()
    out_mesh.name = f"{src_obj.name}_{name_suffix}_mesh"
    bm_out.to_mesh(out_mesh)
    bm_out.free()
    bm.free()
    out_mesh.update()

    # 6. Decimate remaining branches with vertex group mask
    if branch_decimate_ratio < 1.0:
        temp_obj = bpy.data.objects.new("temp_decimate", out_mesh)
        bpy.context.collection.objects.link(temp_obj)
        vg = temp_obj.vertex_groups.new(name="Branches")
        branch_vert_indices = [
            v for poly in out_mesh.polygons if poly.material_index not in leaf_mat_indices
            for v in poly.vertices
        ]
        if branch_vert_indices:
            vg.add(list(set(branch_vert_indices)), 1.0, 'REPLACE')
            mod = temp_obj.modifiers.new(name="Decimate_Branches", type='DECIMATE')
            mod.vertex_group = "Branches"
            mod.ratio = branch_decimate_ratio
            bpy.ops.object.select_all(action='DESELECT')
            temp_obj.select_set(True)
            bpy.context.view_layer.objects.active = temp_obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(temp_obj, do_unlink=True)

    print(f"[Foliage-LOD] Completed {name_suffix}: {len(out_mesh.polygons)} polys, {len(out_mesh.vertices)} verts")
    return out_mesh
#endregion

#region MaterialBake
def bake_leaf_material_gltf(
    mat_name: str,
    diff_name: str,
    opac_name: str,
    trans_name: str,
    norm_name: str,
    refl_name: str = None,
    trans_val: float = 0.5,
    rough_default: float = 0.5
) -> bpy.types.Material:
    """
    Bakes and consolidates multi-texture leaf shader setups (diffuse, opacity, translucency)
    into a standardized, 100% glTF 2.0 compliant PBR material with RGBA BaseColor and Alpha Masking.
    Avoids 3D UV unwrapping issues by processing directly in 2D texture space.
    """
    d_img = bpy.data.images.get(diff_name)
    o_img = bpy.data.images.get(opac_name)
    t_img = bpy.data.images.get(trans_name)
    n_img = bpy.data.images.get(norm_name)
    r_img = bpy.data.images.get(refl_name) if refl_name else None

    w, h = d_img.size
    d_pix = np.array(d_img.pixels[:], dtype=np.float32).reshape((h, w, 4))
    o_pix = np.array(o_img.pixels[:], dtype=np.float32).reshape((h, w, 4))
    t_pix = np.array(t_img.pixels[:], dtype=np.float32).reshape((h, w, 4))

    # Translucency transmission boost into albedo
    trans_mod = t_pix[..., :3] * trans_val
    baked_rgb = np.clip(d_pix[..., :3] + 0.30 * trans_mod, 0.0, 1.0)
    baked_alpha = o_pix[..., 0:1]
    baked_rgba = np.concatenate([baked_rgb, baked_alpha], axis=-1)

    img_name = f"{mat_name}_BaseColor.png"
    baked_img = bpy.data.images.get(img_name)
    if not baked_img or baked_img.size[0] != w or baked_img.size[1] != h:
        if baked_img:
            bpy.data.images.remove(baked_img)
        baked_img = bpy.data.images.new(img_name, width=w, height=h, alpha=True)

    baked_img.pixels = baked_rgba.flatten().tolist()
    baked_img.pack()

    baked_mat_name = f"{mat_name}_Baked"
    baked_mat = bpy.data.materials.get(baked_mat_name)
    if not baked_mat:
        baked_mat = bpy.data.materials.new(baked_mat_name)
    baked_mat.use_nodes = True
    baked_mat.use_backface_culling = False
    baked_mat.blend_method = 'CLIP'
    baked_mat.alpha_threshold = 0.5

    nt = baked_mat.node_tree
    nt.nodes.clear()

    out_node = nt.nodes.new('ShaderNodeOutputMaterial')
    out_node.location = (300, 0)

    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    nt.links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

    tex_base = nt.nodes.new('ShaderNodeTexImage')
    tex_base.name = 'Baked_BaseColor'
    tex_base.image = baked_img
    tex_base.location = (-400, 100)
    nt.links.new(tex_base.outputs['Color'], bsdf.inputs['Base Color'])

    math_clip = nt.nodes.new('ShaderNodeMath')
    math_clip.operation = 'GREATER_THAN'
    math_clip.inputs[1].default_value = 0.5
    math_clip.location = (-150, -50)
    nt.links.new(tex_base.outputs['Alpha'], math_clip.inputs[0])
    nt.links.new(math_clip.outputs['Value'], bsdf.inputs['Alpha'])

    if n_img:
        tex_norm = nt.nodes.new('ShaderNodeTexImage')
        tex_norm.image = n_img
        tex_norm.location = (-400, -200)
        norm_map = nt.nodes.new('ShaderNodeNormalMap')
        norm_map.location = (-150, -200)
        norm_map.inputs['Strength'].default_value = 1.0
        nt.links.new(tex_norm.outputs['Color'], norm_map.inputs['Color'])
        nt.links.new(norm_map.outputs['Normal'], bsdf.inputs['Normal'])

    if r_img:
        tex_refl = nt.nodes.new('ShaderNodeTexImage')
        tex_refl.image = r_img
        tex_refl.location = (-400, -450)
        math_rough = nt.nodes.new('ShaderNodeMath')
        math_rough.operation = 'SUBTRACT'
        math_rough.inputs[0].default_value = 1.0
        math_rough.location = (-150, -450)
        nt.links.new(tex_refl.outputs['Color'], math_rough.inputs[1])
        nt.links.new(math_rough.outputs['Value'], bsdf.inputs['Roughness'])
    else:
        bsdf.inputs['Roughness'].default_value = rough_default

    bsdf.inputs['Metallic'].default_value = 0.0
    print(f"[Foliage-LOD] Baked material {baked_mat_name} configured for glTF.")
    return baked_mat
#endregion

#region AtlasBake
def combine_bush02_materials_to_atlas(obj: bpy.types.Object) -> bpy.types.Material:
    """
    Consolidates 3 materials (Leaf, Branch 02, Branch 03) into a single 2K PBR material atlas.
    Remaps mesh UVs partitioned by column strips, enabling single draw call per instance in WebGPU.
    """
    mat_name = "AE_15TH_FOREST_BUSH_02_Atlas_Mat"
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    mat.blend_method = 'CLIP'
    mat.alpha_threshold = 0.5

    nt = mat.node_tree
    nt.nodes.clear()

    out_node = nt.nodes.new('ShaderNodeOutputMaterial')
    out_node.location = (300, 0)

    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    nt.links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

    tex_base = nt.nodes.new('ShaderNodeTexImage')
    tex_base.name = 'Atlas_BaseColor'
    tex_base.image = bpy.data.images.get('AE_15TH_FOREST_BUSH_02_Atlas_BaseColor.png')
    tex_base.location = (-450, 100)
    nt.links.new(tex_base.outputs['Color'], bsdf.inputs['Base Color'])

    math_clip = nt.nodes.new('ShaderNodeMath')
    math_clip.operation = 'GREATER_THAN'
    math_clip.inputs[1].default_value = 0.5
    math_clip.location = (-150, -50)
    nt.links.new(tex_base.outputs['Alpha'], math_clip.inputs[0])
    nt.links.new(math_clip.outputs['Value'], bsdf.inputs['Alpha'])

    tex_norm = nt.nodes.new('ShaderNodeTexImage')
    tex_norm.image = bpy.data.images.get('AE_15TH_FOREST_BUSH_02_Atlas_Normal.png')
    tex_norm.location = (-450, -200)
    norm_map = nt.nodes.new('ShaderNodeNormalMap')
    norm_map.location = (-150, -200)
    nt.links.new(tex_norm.outputs['Color'], norm_map.inputs['Color'])
    nt.links.new(norm_map.outputs['Normal'], bsdf.inputs['Normal'])

    tex_rough = nt.nodes.new('ShaderNodeTexImage')
    tex_rough.image = bpy.data.images.get('AE_15TH_FOREST_BUSH_02_Atlas_Roughness.png')
    tex_rough.location = (-450, -450)
    nt.links.new(tex_rough.outputs['Color'], bsdf.inputs['Roughness'])

    bsdf.inputs['Metallic'].default_value = 0.0

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.verify()

    for f in bm.faces:
        m_idx = f.material_index
        for loop in f.loops:
            uv = loop[uv_layer].uv
            if m_idx == 0:  # Leaf
                loop[uv_layer].uv = (uv.x * 0.50, uv.y)
            elif m_idx == 1:  # Branch 02
                loop[uv_layer].uv = (0.50 + uv.x * 0.25, uv.y)
            elif m_idx == 2:  # Branch 03
                loop[uv_layer].uv = (0.75 + uv.x * 0.25, uv.y)
        f.material_index = 0

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    obj.data.materials.clear()
    obj.data.materials.append(mat)
    print(f"[Foliage-LOD] {obj.name} unified to single material slot ({mat.name}).")
    return mat
#endregion

#region CrossingBillboard
def create_crossing_billboard_lod3(
    obj_name: str,
    width: float,
    height: float,
    img_filename: str,
    location: tuple,
    collection_name: str = "Optimized_Bushes_LODs"
) -> bpy.types.Object:
    """
    Creates an ultra-lightweight LOD3 crossing billboard (2 intersecting quads at 90 deg / cruciform).
    Reduces polygon count to 2 quads (4 triangles) for distant rendering.
    """
    import os
    full_path = os.path.join(bpy.path.abspath("//"), img_filename)
    img = bpy.data.images.get(img_filename)
    if not img:
        img = bpy.data.images.load(full_path)
    img.pack()

    mat_name = f"{obj_name}_Mat"
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    mat.blend_method = 'CLIP'
    mat.alpha_threshold = 0.5

    nt = mat.node_tree
    nt.nodes.clear()

    out_node = nt.nodes.new('ShaderNodeOutputMaterial')
    out_node.location = (300, 0)

    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    nt.links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

    tex_base = nt.nodes.new('ShaderNodeTexImage')
    tex_base.name = 'Billboard_Texture'
    tex_base.image = img
    tex_base.location = (-400, 100)
    nt.links.new(tex_base.outputs['Color'], bsdf.inputs['Base Color'])

    math_clip = nt.nodes.new('ShaderNodeMath')
    math_clip.operation = 'GREATER_THAN'
    math_clip.inputs[1].default_value = 0.5
    math_clip.location = (-150, -50)
    nt.links.new(tex_base.outputs['Alpha'], math_clip.inputs[0])
    nt.links.new(math_clip.outputs['Value'], bsdf.inputs['Alpha'])

    bsdf.inputs['Roughness'].default_value = 0.6
    bsdf.inputs['Metallic'].default_value = 0.0

    # Auto-detect foreground bounding box in texture to avoid empty padding squishing
    w, h = img.size
    pix = np.array(img.pixels[:], dtype=np.float32).reshape((h, w, 4))
    alpha = pix[:, :, 3]
    rows = np.any(alpha > 0.05, axis=1)
    cols = np.any(alpha > 0.05, axis=0)
    if np.any(rows) and np.any(cols):
        ymin, ymax = np.where(rows)[0][[0, -1]]
        xmin, xmax = np.where(cols)[0][[0, -1]]
        u0, u1 = xmin / w, xmax / w
        v0, v1 = ymin / h, ymax / h
    else:
        u0, u1, v0, v1 = 0.0, 1.0, 0.0, 1.0

    mesh_data = bpy.data.meshes.new(f"{obj_name}_mesh")
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.verify()
    hw = width / 2.0

    # Generate 3 intersecting planes (0, 60, 120 deg) for full 360-degree volumetric presence
    import math
    planes_count = 3
    angles = [i * (math.pi / planes_count) for i in range(planes_count)]
    uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]

    for angle in angles:
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        c0 = (-hw * cos_a, -hw * sin_a, 0.0)
        c1 = ( hw * cos_a,  hw * sin_a, 0.0)
        c2 = ( hw * cos_a,  hw * sin_a, height)
        c3 = (-hw * cos_a, -hw * sin_a, height)
        v_list = [bm.verts.new(c) for c in [c0, c1, c2, c3]]
        f = bm.faces.new(v_list)
        for loop, uv in zip(f.loops, uvs):
            loop[uv_layer].uv = uv

    # Smooth radial normals
    center = mathutils.Vector((0.0, 0.0, height * 0.5))
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        v.normal = (v.co - center).normalized()

    bm.to_mesh(mesh_data)
    bm.free()
    mesh_data.update()

    old_obj = bpy.data.objects.get(obj_name)
    if old_obj:
        bpy.data.objects.remove(old_obj, do_unlink=True)

    billboard_obj = bpy.data.objects.new(obj_name, mesh_data)
    billboard_obj.location = location
    billboard_obj.data.materials.append(mat)

    col = bpy.data.collections.get(collection_name)
    if not col:
        col = bpy.context.scene.collection
    col.objects.link(billboard_obj)
    print(f"[Foliage-LOD] Created full 3-plane billboard {obj_name}: {len(mesh_data.polygons)} quads at {location[:]}")
    return billboard_obj
#endregion



