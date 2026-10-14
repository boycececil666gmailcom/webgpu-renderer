#region InspectMcLaren
import bpy

print("\n================== McLAREN P1 STRUCTURE ==================")
for col in bpy.data.collections:
    print(f"\nCollection: '{col.name}'")
    for obj in col.objects:
        mats = [m.name for m in obj.data.materials if m] if obj.data and hasattr(obj.data, "materials") else []
        parent_name = obj.parent.name if obj.parent else "None"
        print(f"  - {obj.name} (type: {obj.type}, parent: {parent_name}, mats: {mats})")
#endregion

