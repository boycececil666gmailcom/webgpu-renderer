#region Imports
import sys
import bpy
#endregion

#region Types
# No custom types needed for inspector
#endregion

#region Scaffolding
def log_step(title):
    print(f"[STEP] {title}")
#endregion

#region Inspect
def inspect_plant_materials():
    plant_colls = ['01_Small_Plants', '02_Medium_Plants', '03_Large_Plants']
    plant_mats = set()
    for c_name in plant_colls:
        c = bpy.data.collections.get(c_name)
        if not c:
            continue
        for o in c.objects:
            if o.type == 'MESH':
                for m in o.data.materials:
                    if m:
                        plant_mats.add(m.name)

    log_step("=== PLANT MATERIALS INSPECTION ===")
    for m_name in sorted(plant_mats):
        mat = bpy.data.materials.get(m_name)
        if not mat or not mat.use_nodes:
            print(f"Material {m_name}: No node tree")
            continue
        bsdfs = [n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED']
        textures = [n.image.name for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
        print(f"Material {m_name}: PrincipledBSDF={len(bsdfs)}, Textures={textures}")
#endregion

#region Core
def run():
    inspect_plant_materials()
#endregion

#region Main
if __name__ == '__main__':
    run()
    sys.exit(0)
#endregion

