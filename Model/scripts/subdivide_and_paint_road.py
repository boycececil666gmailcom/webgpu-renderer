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
    inner_cutoff_radius: float = 41.0
    outer_edge_radius: float = 49.5
    radial_exponent: float = 1.0
    is_track_wide: bool = True
#endregion

#region Scaffolding
@dataclass(frozen=True)
class RoadConfig:
    object_name: str
    subdiv: RoadSubdivisionConfig
    painting: WeightPaintingConfig

def create_road_config() -> RoadConfig:
    return RoadConfig(
        object_name="ENV_Road_Asphalt_ClosedLoop",
        subdiv=RoadSubdivisionConfig(radial_cuts=9, circumferential_cuts=1),
        painting=WeightPaintingConfig(
            group_name="leaf_density",
            inner_cutoff_radius=41.0,
            outer_edge_radius=49.5,
            radial_exponent=1.0,
            is_track_wide=True
        )
    )
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
    if r < config.inner_cutoff_radius:
        return 0.0
        
    t_radial = min(max((r - config.inner_cutoff_radius) / (config.outer_edge_radius - config.inner_cutoff_radius), 0.0), 1.0)
    w_radial = t_radial ** config.radial_exponent
    
    if config.is_track_wide:
        return w_radial
        
    return w_radial

def author_road_vertex_weights(obj: bpy.types.Object, config: WeightPaintingConfig) -> int:
    mesh = obj.data
    mw = obj.matrix_world
    
    vg = obj.vertex_groups.get(config.group_name)
    if not vg:
        vg = obj.vertex_groups.new(name=config.group_name)
    else:
        for v in mesh.vertices:
            vg.remove([v.index])
            
    non_zero_count = 0
    for v in mesh.vertices:
        w_co = mw @ v.co
        weight = evaluate_leaf_density(w_co, config)
        if weight > 0.0001:
            vg.add([v.index], weight, 'REPLACE')
            non_zero_count += 1
            
    print(f"[WeightPainting] Group '{config.group_name}' authored: {non_zero_count}/{len(mesh.vertices)} non-zero weights")
    return non_zero_count
#endregion

#region Core
def process_road_authoring_core(config: RoadConfig) -> None:
    obj = bpy.data.objects.get(config.object_name)
    if not obj:
        raise ValueError(f"Road object '{config.object_name}' not found in scene")
    subdivide_road_mesh(obj, config.subdiv)
    author_road_vertex_weights(obj, config.painting)
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
