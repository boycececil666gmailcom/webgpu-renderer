#!/usr/bin/env python3
#region Imports
import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
import bmesh
import bpy
#endregion

#region Types
@dataclass(frozen=True)
class RoadUVConfig:
    object_name: str = "ENV_Road_Asphalt_ClosedLoop"
    uv_layer_name: str = "UVMap"
    num_slices: int = 64
    u_repeats: float = 128.0
    v_repeats: float = 4.0
#endregion

#region Scaffolding
def create_config() -> RoadUVConfig:
    return RoadUVConfig()

def log(msg: str) -> None:
    print(f"[RoadUV] {msg}")
#endregion

#region RoadUV
def reproject_road_uvs(mesh: bpy.types.Mesh, config: RoadUVConfig) -> tuple[int, int]:
    # Rename legacy layer if present
    if "Float2" in mesh.uv_layers and config.uv_layer_name not in mesh.uv_layers:
        mesh.uv_layers["Float2"].name = config.uv_layer_name

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Group vertices into angular slices
    slices: dict[int, list[bmesh.types.BMVert]] = defaultdict(list)
    for v in bm.verts:
        theta = math.atan2(v.co.y, v.co.x)
        if theta < 0:
            theta += 2 * math.pi
        idx = int(round((theta / (2 * math.pi)) * config.num_slices)) % config.num_slices
        slices[idx].append(v)

    # Sort each slice radially from inner to outer
    for idx in range(config.num_slices):
        slices[idx].sort(key=lambda vert: math.hypot(vert.co.x, vert.co.y))

    # Map vert -> (slice_idx, radial_idx)
    vert_info: dict[bmesh.types.BMVert, tuple[int, int]] = {}
    for s_idx in range(config.num_slices):
        for r_idx, v in enumerate(slices[s_idx]):
            vert_info[v] = (s_idx, r_idx)

    # Obtain UV layer
    uv_layer = bm.loops.layers.uv.get(config.uv_layer_name)
    if not uv_layer:
        uv_layer = bm.loops.layers.uv.new(config.uv_layer_name)

    regular_quads = 0
    seam_quads = 0

    for f in bm.faces:
        s_indices = [vert_info[v][0] for v in f.verts]
        is_seam = (min(s_indices) == 0 and max(s_indices) == config.num_slices - 1)

        if is_seam:
            seam_quads += 1
        else:
            regular_quads += 1

        for l in f.loops:
            s_idx, r_idx = vert_info[l.vert]

            # Longitudinal continuous U coordinate
            if is_seam and s_idx == 0:
                u = config.u_repeats
            else:
                u = (s_idx / config.num_slices) * config.u_repeats

            # Transverse camber V coordinate (0.0 at inner edge, v_repeats at outer edge)
            v = (r_idx / 10.0) * config.v_repeats

            l[uv_layer].uv = (u, v)

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    for uv in mesh.uv_layers:
        if uv.name == config.uv_layer_name:
            uv.active = True
            uv.active_render = True

    return regular_quads, seam_quads
#endregion

#region Core
def execute_road_uv_reprojection(config: RoadUVConfig) -> None:
    road = bpy.data.objects.get(config.object_name)
    if not road:
        raise ValueError(f"Road object '{config.object_name}' not found")

    log(f"Reprojecting UVs on {road.name}...")
    reg, seam = reproject_road_uvs(road.data, config)
    log(f"Reprojection complete: {reg} regular quads, {seam} seam quads.")

    save_path = bpy.data.filepath
    if save_path:
        bpy.ops.wm.save_mainfile(filepath=save_path)
        log(f"Persisted changes to {save_path}")
#endregion

#region Main
def main() -> int:
    cfg = create_config()
    execute_road_uv_reprojection(cfg)
    return 0

if __name__ == "__main__":
    sys.exit(main())
#endregion
