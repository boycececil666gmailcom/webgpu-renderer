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
class RoadSubdivisionConfig:
    radial_cuts: int = 9
    circumferential_cuts: int = 1

@dataclass(frozen=True)
class WeightPaintingConfig:
    group_name: str = "leaf_density"
    color_attribute_name: str = "leaf_weight"
    inner_cutoff_radius: float = 41.5
    outer_edge_radius: float = 48.0
    radial_exponent: float = 1.0
#endregion

#region Scaffolding
@dataclass(frozen=True)
class RoadAuthoringConfig:
    road_object_name: str = "ENV_Road_Asphalt_ClosedLoop"
    terrain_object_name: str = "ENV_Terrain_Forest_Floor_Layered"
    subdiv: RoadSubdivisionConfig = RoadSubdivisionConfig(radial_cuts=9, circumferential_cuts=1)
    painting: WeightPaintingConfig = WeightPaintingConfig(
        group_name="leaf_density",
        color_attribute_name="leaf_weight",
        inner_cutoff_radius=41.5,
        outer_edge_radius=48.0,
        radial_exponent=1.0,
    )

def create_road_config() -> RoadAuthoringConfig:
    return RoadAuthoringConfig()
#endregion

#region RoadTopology
def subdivide_road_mesh(obj: bpy.types.Object, config: RoadSubdivisionConfig) -> Tuple[int, int]:
    mesh = obj.data
    if len(mesh.vertices) >= 500:
        print(f"[RoadTopology] Object {obj.name} already subdivided ({len(mesh.vertices)} verts), skipping.")
        return len(mesh.vertices), len(mesh.polygons)
        
    bm = bmesh.new()
    bm.from_mesh(mesh)
    
    radial_edges = [
        e for e in bm.edges
        if abs(e.verts[0].co.xy.length - e.verts[1].co.xy.length) > 1.0
    ]
    bmesh.ops.subdivide_edges(bm, edges=radial_edges, cuts=config.radial_cuts, use_grid_fill=True)
    
    circum_edges = [
        e for e in bm.edges
        if abs(e.verts[0].co.xy.length - e.verts[1].co.xy.length) < 0.2
    ]
    bmesh.ops.subdivide_edges(bm, edges=circum_edges, cuts=config.circumferential_cuts, use_grid_fill=True)
    
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    
    vert_count = len(mesh.vertices)
    poly_count = len(mesh.polygons)
    print(f"[RoadTopology] Subdivided {obj.name}: {vert_count} vertices, {poly_count} polygons")
    return vert_count, poly_count
#endregion

#region WeightPainting
def evaluate_leaf_density(world_pos: Vector, config: WeightPaintingConfig) -> float:
    r = world_pos.xy.length
    theta = math.atan2(world_pos.y, world_pos.x)
    # Full coverage across entire road width (40.0m to 48.0m) with natural organic drift
    noise = 0.5 + 0.3 * math.sin(6.0 * theta) * math.cos(4.0 * r) + 0.2 * math.sin(15.0 * theta + 2.0 * r)
    norm_r = min(max((r - 40.0) / 8.0, 0.0), 1.0)
    edge_factor = 1.0 - 4.0 * norm_r * (1.0 - norm_r) # 1.0 at edges, 0.0 at center
    base_weight = 0.70 + 0.15 * edge_factor + 0.15 * noise
    return float(min(max(base_weight, 0.55), 1.0))

def author_road_vertex_weights_and_colors(obj: bpy.types.Object, config: WeightPaintingConfig) -> int:
    mesh = obj.data
    mw = obj.matrix_world

    vg = obj.vertex_groups.get(config.group_name)
    if not vg:
        vg = obj.vertex_groups.new(name=config.group_name)

    ca = mesh.color_attributes.get(config.color_attribute_name)
    if ca is None or ca.domain != 'POINT' or ca.data_type != 'FLOAT_COLOR':
        if ca:
            mesh.color_attributes.remove(ca)
        ca = mesh.color_attributes.new(name=config.color_attribute_name, type='FLOAT_COLOR', domain='POINT')

    mesh.color_attributes.active_color = ca

    non_zero_count = 0
    for v in mesh.vertices:
        w_co = mw @ v.co
        w = evaluate_leaf_density(w_co, config)
        vg.add([v.index], w, 'REPLACE')
        ca.data[v.index].color = (w, w, w, 1.0)
        if w > 0.0001:
            non_zero_count += 1

    print(f"[WeightPainting] Road group '{config.group_name}' & color attribute '{config.color_attribute_name}' authored: {non_zero_count}/{len(mesh.vertices)} non-zero weights")
    return non_zero_count

def zero_terrain_leaf_weights(terrain_obj: bpy.types.Object) -> None:
    vg_leaf = terrain_obj.vertex_groups.get("Leaf_Density")
    if not vg_leaf:
        vg_leaf = terrain_obj.vertex_groups.new(name="Leaf_Density")

    for v in terrain_obj.data.vertices:
        vg_leaf.add([v.index], 0.0, 'REPLACE')

    mesh = terrain_obj.data
    ca_leaf = mesh.color_attributes.get("leaf_weight")
    if ca_leaf is None or ca_leaf.domain != 'POINT' or ca_leaf.data_type != 'FLOAT_COLOR':
        if ca_leaf:
            mesh.color_attributes.remove(ca_leaf)
        ca_leaf = mesh.color_attributes.new(name="leaf_weight", type='FLOAT_COLOR', domain='POINT')

    for d in ca_leaf.data:
        d.color = (0.0, 0.0, 0.0, 1.0)

    ca_scatter = mesh.color_attributes.get("Scatter_Color")
    if ca_scatter:
        mesh.color_attributes.active_color = ca_scatter
        mesh.color_attributes.render_color_index = mesh.color_attributes.find("Scatter_Color")

    print(f"[WeightPainting] Zeroed out Leaf_Density VG & leaf_weight color attribute on {terrain_obj.name}: 0/{len(terrain_obj.data.vertices)} non-zero weights")
#endregion

#region Core
def process_road_authoring_core(config: RoadAuthoringConfig) -> None:
    road_obj = bpy.data.objects.get(config.road_object_name)
    if not road_obj:
        raise ValueError(f"Road object '{config.road_object_name}' not found in scene")

    if len(road_obj.data.vertices) < 500:
        subdivide_road_mesh(road_obj, config.subdiv)

    author_road_vertex_weights_and_colors(road_obj, config.painting)

    terrain_obj = bpy.data.objects.get(config.terrain_object_name)
    if terrain_obj:
        zero_terrain_leaf_weights(terrain_obj)
#endregion

#region Main
def main() -> int:
    config = create_road_config()
    process_road_authoring_core(config)
    save_path = bpy.data.filepath
    if save_path:
        bpy.ops.wm.save_mainfile(filepath=save_path)
        print(f"[Main] Saved changes to {save_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
#endregion
