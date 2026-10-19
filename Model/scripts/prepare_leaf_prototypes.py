#!/usr/bin/env python3
#region Imports
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple
import bpy
#endregion

#region Types
@dataclass(frozen=True)
class LeafMaterialConfig:
    mat_name: str
    texture_filename: str
    roughness: float = 0.75
    metallic: float = 0.0
    alpha_threshold: float = 0.5

@dataclass(frozen=True)
class LeafPrototypeConfig:
    obj_name: str
    material_slots: List[str]
#endregion

#region Scaffolding
@dataclass(frozen=True)
class AssetPreparationConfig:
    textures_dir: str
    collection_name: str
    materials: List[LeafMaterialConfig]
    prototypes: List[LeafPrototypeConfig]

def create_preparation_config() -> AssetPreparationConfig:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    textures_dir = os.path.join(base_dir, "textures")
    
    materials = [
        LeafMaterialConfig("Dry_Leaves_01_PBR", "dry_leaves_01_rgba.png"),
        LeafMaterialConfig("Dry_Leaves_02_PBR", "dry_leaves_02_rgba.png"),
        LeafMaterialConfig("Dry_Leaves_03_PBR", "dry_leaves_03_rgba.png"),
    ]
    
    prototypes = [
        LeafPrototypeConfig("AE_15TH_DRY_LEAVES_01", ["Dry_Leaves_01_PBR"]),
        LeafPrototypeConfig("AE_15TH_DRY_LEAVES_02", ["Dry_Leaves_02_PBR", "Dry_Leaves_03_PBR"]),
        LeafPrototypeConfig("AE_15TH_DRY_LEAVES_03", ["Dry_Leaves_01_PBR", "Dry_Leaves_02_PBR", "Dry_Leaves_03_PBR"]),
    ]
    
    return AssetPreparationConfig(
        textures_dir=textures_dir,
        collection_name="Foliage_Leaves_Prototypes",
        materials=materials,
        prototypes=prototypes
    )
#endregion

#region Foliage
def get_or_create_collection(col_name: str) -> bpy.types.Collection:
    col = bpy.data.collections.get(col_name)
    if not col:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)
    return col

def build_pbr_leaf_material(mat_cfg: LeafMaterialConfig, textures_dir: str) -> bpy.types.Material:
    mat = bpy.data.materials.get(mat_cfg.mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_cfg.mat_name)
        
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    tex_path = os.path.join(textures_dir, mat_cfg.texture_filename)
    img = bpy.data.images.get(mat_cfg.texture_filename)
    if not img or img.filepath != tex_path:
        img = bpy.data.images.load(tex_path, check_existing=True)
    img.alpha_mode = 'STRAIGHT'
    
    node_tex = nodes.new(type="ShaderNodeTexImage")
    node_tex.image = img
    node_tex.location = (-300, 0)
    
    node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    node_bsdf.location = (0, 0)
    node_bsdf.inputs["Roughness"].default_value = mat_cfg.roughness
    node_bsdf.inputs["Metallic"].default_value = mat_cfg.metallic
    if "Specular IOR Level" in node_bsdf.inputs:
        node_bsdf.inputs["Specular IOR Level"].default_value = 0.5
        
    node_out = nodes.new(type="ShaderNodeOutputMaterial")
    node_out.location = (300, 0)
    
    node_math = nodes.new(type="ShaderNodeMath")
    node_math.operation = 'GREATER_THAN'
    node_math.inputs[1].default_value = mat_cfg.alpha_threshold
    node_math.location = (-150, -100)

    links.new(node_tex.outputs["Color"], node_bsdf.inputs["Base Color"])
    links.new(node_tex.outputs["Alpha"], node_math.inputs[0])
    links.new(node_math.outputs["Value"], node_bsdf.inputs["Alpha"])
    links.new(node_bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    
    mat.use_backface_culling = False
    return mat

def configure_leaf_object(proto_cfg: LeafPrototypeConfig, target_col: bpy.types.Collection) -> None:
    obj = bpy.data.objects.get(proto_cfg.obj_name)
    if not obj:
        raise ValueError(f"Leaf object {proto_cfg.obj_name} not found in blend file")
        
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    target_col.objects.link(obj)
    
    while len(obj.data.materials) < len(proto_cfg.material_slots):
        obj.data.materials.append(None)
    for i, mat_name in enumerate(proto_cfg.material_slots):
        mat = bpy.data.materials.get(mat_name)
        obj.material_slots[i].material = mat
        
    print(f"[LeafPrototype] Configured {obj.name} with materials: {[s.name for s in obj.material_slots]}")

def purge_orphan_data() -> None:
    for block in bpy.data.materials:
        if block.users == 0 and ("Dry_Leaves" in block.name or "Ever_cabins" in block.name):
            bpy.data.materials.remove(block)
    for block in bpy.data.images:
        if block.users == 0 and ("Ever_cabins" in block.name or "opacity" in block.name):
            bpy.data.images.remove(block)
#endregion

#region Core
def prepare_leaf_prototypes_core(config: AssetPreparationConfig) -> None:
    target_col = get_or_create_collection(config.collection_name)
    for mat_cfg in config.materials:
        build_pbr_leaf_material(mat_cfg, config.textures_dir)
    for proto_cfg in config.prototypes:
        configure_leaf_object(proto_cfg, target_col)
    purge_orphan_data()
#endregion

#region Main
def main() -> int:
    config = create_preparation_config()
    prepare_leaf_prototypes_core(config)
    save_path = bpy.data.filepath
    if save_path:
        bpy.ops.wm.save_mainfile(filepath=save_path)
        print(f"[LeafPrototype] Saved {save_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
#endregion
