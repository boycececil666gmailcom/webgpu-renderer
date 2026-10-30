#region Imports
import bpy
#endregion

#region Scaffolding
def print_mclaren_structure() -> None:
    print("\n================== McLAREN P1 STRUCTURE ==================")
    for col in bpy.data.collections:
        print(f"\nCollection: '{col.name}'")
        for obj in col.objects:
            mats = [m.name for m in obj.data.materials if m] if obj.data and hasattr(obj.data, "materials") else []
            parent_name = obj.parent.name if obj.parent else "None"
            print(f"  - {obj.name} (type: {obj.type}, parent: {parent_name}, mats: {mats})")
#endregion

#region Core
def main() -> None:
    print_mclaren_structure()

if __name__ == "__main__":
    main()
#endregion
