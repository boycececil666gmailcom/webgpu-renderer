import bpy
import math

terrain = bpy.data.objects.get("ENV_Terrain_Forest_Floor_Layered")
cam = bpy.data.objects.get("CAM_Scene_Follow")
car = bpy.data.objects.get("Revuelto.Body")

cam_x, cam_y = cam.location.x, cam.location.y
car_x, car_y = car.location.x, car.location.y

# Line of sight segment
vx, vy = car_x - cam_x, car_y - cam_y
v_len_sq = vx*vx + vy*vy
v_len = math.sqrt(v_len_sq)

mesh = terrain.data
color_attr = mesh.color_attributes.get("Scatter_Color")
if not color_attr:
    color_attr = mesh.color_attributes.new(name="Scatter_Color", type='FLOAT_COLOR', domain='POINT')

mat = terrain.matrix_world

# Vertex group references
vg_scatter = terrain.vertex_groups.get("Scatter_Density")
if not vg_scatter:
    vg_scatter = terrain.vertex_groups.new(name="Scatter_Density")
vg_undergrowth = terrain.vertex_groups.get("Undergrowth_Density")
if not vg_undergrowth:
    vg_undergrowth = terrain.vertex_groups.new(name="Undergrowth_Density")

updated = 0
for i, v in enumerate(mesh.vertices):
    w = mat @ v.co
    wx, wy = w.x, w.y
    r = math.sqrt(wx*wx + wy*wy)
    
    # Distance to camera
    d_cam = math.sqrt((wx - cam_x)**2 + (wy - cam_y)**2)
    
    # Distance to line of sight
    t = ((wx - cam_x)*vx + (wy - cam_y)*vy) / v_len_sq
    t_clamped = max(0.0, min(1.0, t))
    proj_x = cam_x + t_clamped * vx
    proj_y = cam_y + t_clamped * vy
    d_los = math.sqrt((wx - proj_x)**2 + (wy - proj_y)**2)
    
    # Camera / LOS clearance masks
    tree_cam_clear = 0.0 if d_cam < 6.5 else (min(1.0, (d_cam - 6.5) / 2.0))
    if t > -0.1 and t < 1.1 and d_los < 3.2:
        tree_cam_clear *= min(1.0, d_los / 3.2)
        
    bush_cam_clear = 0.0 if d_cam < 4.2 else (min(1.0, (d_cam - 4.2) / 1.5))
    if t > -0.1 and t < 1.0 and d_los < 2.0:
        bush_cam_clear *= min(1.0, d_los / 2.0)
        
    rock_cam_clear = 0.0 if d_cam < 3.5 else 1.0
    
    # --- R: Tree density ---
    # Road driving surface clearance: [39.5, 48.5]
    if r < 37.0:
        base_r = 0.85
    elif r < 39.5:
        # inner shoulder transition
        base_r = 0.85 * (1.0 - (r - 37.0) / 2.5)
    elif r <= 48.5:
        # road asphalt
        base_r = 0.0
    elif r < 52.0:
        # outer shoulder transition
        base_r = 0.85 * ((r - 48.5) / 3.5)
    else:
        base_r = 0.85
    
    val_r = max(0.0, min(0.85, base_r * tree_cam_clear))
    
    # --- G: Undergrowth / Green Bushes ---
    # High density along shoulders: inner [36.5, 40.2], outer [47.8, 51.5]
    # Driving asphalt clearance: [40.5, 47.5] = 0.0
    if r < 36.0:
        base_g = 0.45
    elif r < 38.5:
        # rising up to inner shoulder peak
        base_g = 0.45 + 0.50 * ((r - 36.0) / 2.5) # up to 0.95
    elif r < 40.2:
        # inner shoulder peak
        base_g = 0.95 * (1.0 - (r - 38.5) / 1.7 * 0.4) # 0.95 down to 0.57
    elif r < 40.8:
        base_g = 0.57 * (1.0 - (r - 40.2) / 0.6)
    elif r <= 47.2:
        # asphalt surface
        base_g = 0.0
    elif r < 48.0:
        # rising up from road edge to outer shoulder
        base_g = 0.95 * ((r - 47.2) / 0.8)
    elif r < 51.5:
        # outer shoulder peak
        base_g = 0.95 - 0.45 * ((r - 48.0) / 3.5) # 0.95 down to 0.50
    else:
        # forest interior
        base_g = 0.45
        
    val_g = max(0.0, min(0.98, base_g * bush_cam_clear))
    
    # --- B: Rocks ---
    if r > 39.5 and r < 48.5:
        base_b = 0.0
    elif r >= 36.5 and r <= 39.5:
        base_b = 0.55 * (1.0 - abs(r - 38.0) / 1.5)
    elif r >= 48.5 and r <= 52.0:
        base_b = 0.55 * (1.0 - abs(r - 50.0) / 1.5)
    else:
        base_b = 0.30
    val_b = max(0.0, min(1.0, base_b * rock_cam_clear))
    
    color_attr.data[i].color = (val_r, val_g, val_b, 1.0)
    vg_scatter.add([i], val_r, 'REPLACE')
    vg_undergrowth.add([i], val_g, 'REPLACE')
    updated += 1

print(f"Updated {updated} vertices on {terrain.name}")
