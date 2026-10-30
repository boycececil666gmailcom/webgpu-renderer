import os
import math
import bpy

def run():
    print("[REFINE] Starting terrain and road weight refinements...")
    
    terrain = bpy.data.objects.get("ENV_Terrain_Forest_Floor_Layered")
    cam = bpy.data.objects.get("CAM_Scene_Follow")
    car = bpy.data.objects.get("Revuelto.Body")
    road = bpy.data.objects.get("ENV_Road_Asphalt_ClosedLoop")
    
    assert terrain is not None, "Terrain object missing"
    assert cam is not None, "Camera object missing"
    assert car is not None, "Car object missing"
    assert road is not None, "Road object missing"
    
    cam_x, cam_y = cam.location.x, cam.location.y
    car_x, car_y = car.location.x, car.location.y
    print(f"[REFINE] Camera: ({cam_x:.2f}, {cam_y:.2f}), Car: ({car_x:.2f}, {car_y:.2f})")
    
    vx, vy = car_x - cam_x, car_y - cam_y
    v_len_sq = vx*vx + vy*vy
    
    # 1. Update Terrain weights
    t_mesh = terrain.data
    color_attr = t_mesh.color_attributes.get("Scatter_Color")
    if not color_attr:
        color_attr = t_mesh.color_attributes.new(name="Scatter_Color", type='FLOAT_COLOR', domain='POINT')
        
    vg_scatter = terrain.vertex_groups.get("Scatter_Density") or terrain.vertex_groups.new(name="Scatter_Density")
    vg_undergrowth = terrain.vertex_groups.get("Undergrowth_Density") or terrain.vertex_groups.new(name="Undergrowth_Density")
    
    mat_t = terrain.matrix_world
    for i, v in enumerate(t_mesh.vertices):
        w = mat_t @ v.co
        wx, wy = w.x, w.y
        r = math.sqrt(wx*wx + wy*wy)
        d_cam = math.sqrt((wx - cam_x)**2 + (wy - cam_y)**2)
        d_car = math.sqrt((wx - car_x)**2 + (wy - car_y)**2)
        
        t = ((wx - cam_x)*vx + (wy - cam_y)*vy) / v_len_sq
        t_clamped = max(0.0, min(1.0, t))
        proj_x = cam_x + t_clamped * vx
        proj_y = cam_y + t_clamped * vy
        d_los = math.sqrt((wx - proj_x)**2 + (wy - proj_y)**2)
        
        # Tree cam & corridor clearance
        tree_cam_clear = 0.0 if d_cam < 8.5 else min(1.0, (d_cam - 8.5) / 2.5)
        if -0.2 < t < 1.2:
            if d_los < 5.5:
                tree_cam_clear *= 0.0 if d_los < 3.5 else (d_los - 3.5) / 2.0
        if d_car < 4.5:
            tree_cam_clear *= max(0.0, (d_car - 3.0) / 1.5)
            
        # Bush cam & corridor clearance
        bush_cam_clear = 0.0 if d_cam < 6.5 else min(1.0, (d_cam - 6.5) / 2.0)
        if -0.2 < t < 1.2:
            if d_los < 3.8:
                bush_cam_clear *= 0.0 if d_los < 2.2 else (d_los - 2.2) / 1.6
        if d_car < 4.0:
            bush_cam_clear *= max(0.0, (d_car - 2.5) / 1.5)
            
        rock_cam_clear = 0.0 if d_cam < 4.0 else 1.0
        
        # --- R: Tree density ---
        if r < 36.5:
            base_r = 0.85
        elif r < 37.5:
            base_r = 0.85 * (1.0 - (r - 36.5) / 1.0)
        elif r <= 50.0:
            base_r = 0.0
        elif r < 51.5:
            base_r = 0.85 * ((r - 50.0) / 1.5)
        else:
            base_r = 0.85
        val_r = max(0.0, min(0.85, base_r * tree_cam_clear))
        
        # --- G: Undergrowth / Green Bushes ---
        # Driving surface clearance: [39.2, 48.8] strictly 0.0
        # Inner shoulder: [35.5, 39.2] with peak 0.98 hugging inner curb
        # Outer shoulder: [48.8, 52.5] with peak 0.98 hugging outer curb
        if r < 33.0:
            base_g = 0.45
        elif r < 35.5:
            base_g = 0.45 + 0.53 * ((r - 33.0) / 2.5) # ramp up to 0.98
        elif r <= 39.2:
            base_g = 0.98 # rich lush green bushes hugging inner curb
        elif r <= 48.8:
            base_g = 0.0 # strictly 0 on road
        elif r < 52.5:
            base_g = 0.98 # rich lush green bushes hugging outer curb
        elif r < 55.0:
            base_g = 0.98 - 0.53 * ((r - 52.5) / 2.5) # ramp down to 0.45
        else:
            base_g = 0.45
        val_g = max(0.0, min(0.98, base_g * bush_cam_clear))
        
        # --- B: Rocks ---
        if 39.2 <= r <= 48.8:
            base_b = 0.0
        elif 37.0 <= r < 39.2:
            base_b = 0.65
        elif 48.8 < r <= 51.0:
            base_b = 0.65
        else:
            base_b = 0.25
        val_b = max(0.0, min(1.0, base_b * rock_cam_clear))
        
        color_attr.data[i].color = (val_r, val_g, val_b, 1.0)
        vg_scatter.add([i], val_r, 'REPLACE')
        vg_undergrowth.add([i], val_g, 'REPLACE')

    print(f"[REFINE] Updated {len(t_mesh.vertices)} terrain vertices.")

    # 2. Update Road leaf weights
    r_mesh = road.data
    r_color_attr = r_mesh.color_attributes.get("leaf_weight") or r_mesh.color_attributes.new(name="leaf_weight", type='FLOAT_COLOR', domain='POINT')
    r_scatter_attr = r_mesh.color_attributes.get("Scatter_Color") or r_mesh.color_attributes.new(name="Scatter_Color", type='FLOAT_COLOR', domain='POINT')
    vg_leaf = road.vertex_groups.get("leaf_density") or road.vertex_groups.new(name="leaf_density")

    mat_r = road.matrix_world
    for i, v in enumerate(r_mesh.vertices):
        w = mat_r @ v.co
        wx, wy = w.x, w.y
        r = math.sqrt(wx*wx + wy*wy)
        theta = math.atan2(wy, wx)
        
        # Natural fallen leaf distribution across entire road
        edge_dist = min(r - 40.0, 48.0 - r)
        base_leaf = 0.95 - 0.08 * (edge_dist / 4.0) + 0.06 * math.sin(7.0 * theta) * math.cos(2.0 * r)
        val_leaf = max(0.75, min(1.0, base_leaf))
        
        r_color_attr.data[i].color = (val_leaf, val_leaf, val_leaf, 1.0)
        r_scatter_attr.data[i].color = (val_leaf, val_leaf, val_leaf, 1.0)
        vg_leaf.add([i], val_leaf, 'REPLACE')

    print(f"[REFINE] Updated {len(r_mesh.vertices)} road vertices.")
    
    # Save blend file
    bpy.ops.wm.save_mainfile()
    print("[REFINE] Saved Model/asset.blend.")
    
    # Select objects for gltf export
    bpy.ops.object.select_all(action='DESELECT')
    
    car_root = bpy.data.objects.get("Revuelto.Body")
    if car_root:
        car_root.select_set(True)
    car_coll = bpy.data.collections.get("Lamborghini_Revuelto")
    if car_coll:
        for obj in car_coll.all_objects:
            obj.select_set(True)
            
    for name in ["ENV_Road_Asphalt_ClosedLoop", "ENV_Terrain_Forest_Floor_Layered", "ENV_Sky_Column", "CAM_Scene_Follow", "Sun"]:
        o = bpy.data.objects.get(name)
        if o:
            o.select_set(True)
            
    blend_dir = bpy.path.abspath("//")
    project_root = os.path.abspath(os.path.join(blend_dir, ".."))
    glb_path = os.path.join(project_root, "assets", "models", "base_scene.glb")
    
    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        use_selection=True,
        export_format='GLB',
        export_apply=False,
        export_materials='EXPORT',
        export_image_format='AUTO',
        export_cameras=True,
        export_lights=True
    )
    print(f"[REFINE] Exported {glb_path} ({os.path.getsize(glb_path)} bytes).")

if __name__ == '__main__':
    run()
