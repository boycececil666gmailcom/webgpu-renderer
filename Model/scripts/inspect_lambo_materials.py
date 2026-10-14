#region InspectLamboFull
import bpy

with open("scripts/lambo_objects.txt", "w", encoding="utf-8") as f:
    f.write("================== LAMBORGHINI REVUELTO ALL OBJECTS ==================\n")
    lambo_root = bpy.data.objects.get("EMP_Lamborghini_Revuelto")
    if lambo_root:
        children = [o for o in bpy.data.objects if o.parent == lambo_root]
        f.write(f"Total children: {len(children)}\n\n")
        for obj in sorted(children, key=lambda x: x.name):
            mats = [m.name for m in obj.data.materials if m] if obj.data and hasattr(obj.data, "materials") else []
            cols = [c.name for c in obj.users_collection]
            f.write(f"'{obj.name}' | cols: {cols} | mats: {mats} | dims: ({obj.dimensions.x:.3f}, {obj.dimensions.y:.3f}, {obj.dimensions.z:.3f}) | loc: ({obj.location.x:.3f}, {obj.location.y:.3f}, {obj.location.z:.3f})\n")
#endregion

