import json, math
import bpy
from mathutils import Vector

cam = bpy.data.objects.get("CAM_Scene_Follow")
cam_pos = cam.location # Blender loc: (-49.71, 11.60, 1.29)
# In glTF coords: (x, z, -y): (-49.71, 1.29, -11.60)
print(f"Blender Cam pos: {cam_pos}")

terrain = bpy.data.objects.get("ENV_Terrain_Forest_Floor_Layered")
mesh = terrain.data

# Check vertex colors / groups
print("Color attributes:", [c.name for c in mesh.color_attributes])
print("Vertex groups:", [g.name for g in terrain.vertex_groups])

# Let's inspect weights near the camera in Blender
# Camera is at X=-49.71, Y=11.60. Distance from origin: r = sqrt((-49.71)^2 + 11.6^2) = sqrt(2471 + 134.5) = 51.04 meters!
print(f"Camera radius from origin: {math.sqrt(cam_pos.x**2 + cam_pos.y**2):.2f}m")
car = bpy.data.objects.get("Revuelto.Body")
car_pos = car.location
print(f"Car loc: {car_pos}, radius: {math.sqrt(car_pos.x**2 + car_pos.y**2):.2f}m")
