#!/usr/bin/env python3
#region Imports
import math
import os
import sys
from dataclasses import dataclass
from typing import Tuple
import bmesh
import bpy
from mathutils import Vector
#endregion

#region Types
@dataclass(frozen=True)
class ScatterParams:
    distance_min: float = 0.14
    density_max: float = 30.0
    noise_scale: float = 0.5
    scale_min: float = 0.85
    scale_max: float = 1.35
    normal_offset_z: float = 0.008

@dataclass(frozen=True)
class ScatterConfig:
    road_object_name: str
    collection_name: str
    modifier_name: str
    node_tree_name: str
    scatter_object_name: str
    params: ScatterParams
#endregion

#region Scaffolding
def create_default_scatter_config() -> ScatterConfig:
    return ScatterConfig(
        road_object_name="ENV_Road_Asphalt_ClosedLoop",
        collection_name="Foliage_Leaves_Prototypes",
        modifier_name="GEO_Scatter_Leaves",
        node_tree_name="GEO_Scatter_Leaves",
        scatter_object_name="ENV_Foliage_Leaves_Scatter",
        params=ScatterParams()
    )
#endregion

#region GeometryNodes
def build_scatter_node_tree(config: ScatterConfig, col_leaves: bpy.types.Collection) -> bpy.types.NodeTree:
    old_nt = bpy.data.node_groups.get(config.node_tree_name)
    if old_nt:
        bpy.data.node_groups.remove(old_nt)
        
    nt = bpy.data.node_groups.new(name=config.node_tree_name, type="GeometryNodeTree")
    
    nt.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    nt.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    
    n_in = nt.nodes.new("NodeGroupInput")
    n_in.location = (-600, 0)
    
    n_out = nt.nodes.new("NodeGroupOutput")
    n_out.location = (800, 0)
    
    n_attr = nt.nodes.new("GeometryNodeInputNamedAttribute")
    n_attr.data_type = 'FLOAT'
    n_attr.inputs["Name"].default_value = "leaf_density"
    n_attr.location = (-600, -200)
    
    n_noise = nt.nodes.new("ShaderNodeTexNoise")
    n_noise.inputs["Scale"].default_value = config.params.noise_scale
    n_noise.location = (-600, -400)
    
    n_math_mult = nt.nodes.new("ShaderNodeMath")
    n_math_mult.operation = 'MULTIPLY'
    n_math_mult.location = (-350, -200)
    
    n_dist = nt.nodes.new("GeometryNodeDistributePointsOnFaces")
    n_dist.distribute_method = 'POISSON'
    n_dist.inputs["Distance Min"].default_value = config.params.distance_min
    n_dist.inputs["Density Max"].default_value = config.params.density_max
    n_dist.location = (-100, -200)
    
    n_col = nt.nodes.new("GeometryNodeCollectionInfo")
    n_col.inputs["Collection"].default_value = col_leaves
    n_col.inputs["Separate Children"].default_value = True
    n_col.inputs["Reset Children"].default_value = True
    n_col.location = (-100, -450)
    
    n_inst = nt.nodes.new("GeometryNodeInstanceOnPoints")
    n_inst.inputs["Pick Instance"].default_value = True
    n_inst.location = (150, -200)
    
    n_rand_yaw = nt.nodes.new("FunctionNodeRandomValue")
    n_rand_yaw.data_type = 'FLOAT_VECTOR'
    for inp in n_rand_yaw.inputs:
        if inp.type == 'VECTOR' and inp.name == 'Min':
            inp.default_value = Vector((-0.08, -0.08, 0.0))
        elif inp.type == 'VECTOR' and inp.name == 'Max':
            inp.default_value = Vector((0.08, 0.08, 2.0 * math.pi))
    n_rand_yaw.location = (150, -450)
    
    n_rand_scale = nt.nodes.new("FunctionNodeRandomValue")
    n_rand_scale.data_type = 'FLOAT'
    n_rand_scale.inputs[2].default_value = config.params.scale_min
    n_rand_scale.inputs[3].default_value = config.params.scale_max
    n_rand_scale.location = (150, -650)
    
    n_rot = nt.nodes.new("GeometryNodeRotateInstances")
    n_rot.inputs["Local Space"].default_value = True
    n_rot.location = (350, -200)
    
    n_trans = nt.nodes.new("GeometryNodeTranslateInstances")
    n_trans.inputs["Translation"].default_value = Vector((0.0, 0.0, config.params.normal_offset_z))
    n_trans.inputs["Local Space"].default_value = True
    n_trans.location = (450, -200)
    
    n_realize = nt.nodes.new("GeometryNodeRealizeInstances")
    n_realize.location = (550, -200)
    
    n_join = nt.nodes.new("GeometryNodeJoinGeometry")
    n_join.location = (650, 0)
    
    links = nt.links
    links.new(n_in.outputs["Geometry"], n_join.inputs["Geometry"])
    links.new(n_in.outputs["Geometry"], n_dist.inputs["Mesh"])
    links.new(n_attr.outputs["Attribute"], n_math_mult.inputs[0])
    links.new(n_noise.outputs["Factor"], n_math_mult.inputs[1])
    links.new(n_math_mult.outputs["Value"], n_dist.inputs["Density Factor"])
    links.new(n_dist.outputs["Points"], n_inst.inputs["Points"])
    links.new(n_dist.outputs["Rotation"], n_inst.inputs["Rotation"])
    links.new(n_col.outputs["Instances"], n_inst.inputs["Instance"])
    links.new(n_rand_scale.outputs[1], n_inst.inputs["Scale"])
    links.new(n_inst.outputs["Instances"], n_rot.inputs["Instances"])
    
    rand_vec_out = [out for out in n_rand_yaw.outputs if out.type == 'VECTOR'][0]
    links.new(rand_vec_out, n_rot.inputs["Rotation"])
    links.new(n_rot.outputs["Instances"], n_trans.inputs["Instances"])
    links.new(n_trans.outputs["Instances"], n_realize.inputs["Geometry"])
    links.new(n_realize.outputs["Geometry"], n_join.inputs["Geometry"])
    links.new(n_join.outputs["Geometry"], n_out.inputs["Geometry"])
    
    return nt

def apply_scatter_modifier(obj: bpy.types.Object, nt: bpy.types.NodeTree, config: ScatterConfig) -> None:
    for mod in list(obj.modifiers):
        if mod.name == config.modifier_name:
            obj.modifiers.remove(mod)
    mod = obj.modifiers.new(name=config.modifier_name, type='NODES')
    mod.node_group = nt

def sync_scatter_carrier_mesh(road: bpy.types.Object, config: ScatterConfig) -> Tuple[int, int]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = road.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    
    scatter_obj = bpy.data.objects.get(config.scatter_object_name)
    if not scatter_obj:
        mesh_data = bpy.data.meshes.new(f"{config.scatter_object_name}_Mesh")
        scatter_obj = bpy.data.objects.new(config.scatter_object_name, mesh_data)
        bpy.context.scene.collection.objects.link(scatter_obj)
        
    scatter_obj.data = eval_mesh.copy()
    scatter_obj.matrix_world = road.matrix_world
    
    bm = bmesh.new()
    bm.from_mesh(scatter_obj.data)
    road_faces = [
        f for f in bm.faces 
        if f.material_index < len(scatter_obj.data.materials) and "Road" in scatter_obj.data.materials[f.material_index].name
    ]
    if road_faces:
        bmesh.ops.delete(bm, geom=road_faces, context='FACES')
        bm.to_mesh(scatter_obj.data)
    bm.free()
    
    for slot in list(scatter_obj.material_slots):
        if "Road" in slot.name:
            idx = scatter_obj.data.materials.find(slot.name)
            if idx >= 0:
                scatter_obj.data.materials.pop(index=idx)
                
    scatter_obj.data.update()
    eval_obj.to_mesh_clear()
    
    return len(scatter_obj.data.vertices), len(scatter_obj.data.polygons)
#endregion

#region Core
def setup_scatter_core(config: ScatterConfig) -> Tuple[int, int]:
    road = bpy.data.objects.get(config.road_object_name)
    if not road:
        raise ValueError(f"Road object '{config.road_object_name}' not found")
    col = bpy.data.collections.get(config.collection_name)
    if not col:
        raise ValueError(f"Prototypes collection '{config.collection_name}' not found")
        
    nt = build_scatter_node_tree(config, col)
    apply_scatter_modifier(road, nt, config)
    v_count, p_count = sync_scatter_carrier_mesh(road, config)
    print(f"[Core] Synchronized scatter carrier: {v_count} vertices, {p_count} polygons")
    return v_count, p_count
#endregion

#region Main
def main() -> int:
    config = create_default_scatter_config()
    setup_scatter_core(config)
    save_path = bpy.data.filepath
    if save_path:
        bpy.ops.wm.save_mainfile(filepath=save_path)
        print(f"[Main] Saved changes to {save_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
#endregion

