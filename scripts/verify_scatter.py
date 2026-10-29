import bisect
import json
import math
import os
import struct

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
config_path = os.path.join(repo_root, "config", "scatter.json")
glb_path = os.path.join(repo_root, "gltf", "base_scene.glb")

print(f"=== 1. Validating Scatter Configuration: {config_path} ===")
with open(config_path, "r", encoding="utf-8") as f:
    rules = json.load(f)

leaf_rules = [r for r in rules if "leaf" in r["name"] or "leaves" in r["name"]]
print(f"Leaf rules found: {len(leaf_rules)}")
for r in leaf_rules:
    print(f"  Rule '{r['name']}': target='{r['target_surface_node']}', enabled={r['enabled']}, count={r['count']}, weight_ch={r.get('weight_channel')}, comp={r.get('weight_component')}")
    assert r["target_surface_node"] == "ENV_Road_Asphalt_ClosedLoop", f"Expected target road, got {r['target_surface_node']}"
    assert r["enabled"] is True, "Leaf rule should be enabled"
    assert r["count"] > 0, "Leaf count should be > 0"
    for lod in r.get("lods", []):
        proto_path = os.path.join(repo_root, "gltf", lod["prototype_asset"])
        assert os.path.isfile(proto_path), f"Leaf prototype file not found: {proto_path}"
        print(f"    LOD{lod['lod_level']}: {lod['prototype_asset']} exists ({os.path.getsize(proto_path)} bytes)")

terrain_rules = [r for r in rules if r.get("target_surface_node") == "ENV_Terrain_Forest_Floor_Layered"]
print(f"Terrain rules found: {len(terrain_rules)}")
for r in terrain_rules:
    assert "leaf" not in r["name"] and "leaves" not in r["name"], f"Terrain rule {r['name']} contains leaf/leaves!"
    assert r["enabled"] is True, f"Terrain rule {r['name']} is disabled!"
    print(f"  Terrain rule: {r['name']} (count={r['count']})")

print(f"\n=== 2. Validating Binary glTF Surface Attributes: {glb_path} ===")
with open(glb_path, "rb") as f:
    f.seek(12)
    chunk0_len, _ = struct.unpack("<II", f.read(8))
    data = json.loads(f.read(chunk0_len).decode("utf-8"))
    f.seek(20 + chunk0_len)
    chunk1_len, _ = struct.unpack("<II", f.read(8))
    bin_data = f.read(chunk1_len)

def get_accessor_floats(acc_idx, comp=0):
    acc = data["accessors"][acc_idx]
    bv = data["bufferViews"][acc["bufferView"]]
    offset = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    count = acc["count"]
    ctype = acc["componentType"]
    norm = 65535.0 if ctype == 5123 else (255.0 if ctype == 5121 else 1.0)
    fmt = "H" if ctype == 5123 else ("B" if ctype == 5121 else "f")
    stride = bv.get("byteStride", struct.calcsize(fmt)*4)
    vals = []
    for i in range(count):
        c = struct.unpack_from(f"<{fmt*4}", bin_data, offset + i * stride)
        vals.append(c[comp] / norm)
    return vals

# Road vertex color verification
road_node = [n for n in data["nodes"] if n.get("name") == "ENV_Road_Asphalt_ClosedLoop"][0]
road_mesh = data["meshes"][road_node["mesh"]]
road_prim = road_mesh["primitives"][0]
assert "COLOR_1" in road_prim["attributes"], "Road primitive missing COLOR_1"
road_weights = get_accessor_floats(road_prim["attributes"]["COLOR_1"], comp=0)
min_rw, max_rw = min(road_weights), max(road_weights)
non_zero_rw = sum(1 for w in road_weights if w > 0.001)
zero_rw = sum(1 for w in road_weights if w <= 0.001)
print(f"Road COLOR_1 weights: count={len(road_weights)}, min={min_rw:.3f}, max={max_rw:.3f}, non_zeros={non_zero_rw}, zeros={zero_rw}")
assert min_rw == 0.0, "Inner road edge should have zero weight"
assert max_rw >= 0.99, "Outer road edge should have max weight ~1.0"
assert zero_rw > 0, "Clean inner driving lane must have zero weights"

# Terrain vertex color verification
terrain_node = [n for n in data["nodes"] if n.get("name") == "ENV_Terrain_Forest_Floor_Layered"][0]
terrain_mesh = data["meshes"][terrain_node["mesh"]]
terrain_prim = terrain_mesh["primitives"][0]
assert "COLOR_1" in terrain_prim["attributes"], "Terrain primitive missing COLOR_1 (Scatter_Color)"
assert "COLOR_2" in terrain_prim["attributes"], "Terrain primitive missing COLOR_2 (leaf_weight)"

terrain_leaf_weights = get_accessor_floats(terrain_prim["attributes"]["COLOR_2"], comp=0)
print(f"Terrain COLOR_2 (leaf_weight): count={len(terrain_leaf_weights)}, min={min(terrain_leaf_weights):.3f}, max={max(terrain_leaf_weights):.3f}")
non_zero_terrain_leaves = sum(1 for w in terrain_leaf_weights if w > 0.001)
print(f"Terrain non-zero leaf weights in COLOR_2: {non_zero_terrain_leaves}")
assert non_zero_terrain_leaves == 0, f"Expected 0 non-zero leaf weights on terrain, found {non_zero_terrain_leaves}!"

terrain_r_weights = get_accessor_floats(terrain_prim["attributes"]["COLOR_1"], comp=0)
terrain_b_weights = get_accessor_floats(terrain_prim["attributes"]["COLOR_1"], comp=2)
print(f"Terrain COLOR_1 Scatter_Color: R(trees/foliage) non-zero={sum(1 for w in terrain_r_weights if w > 0.001)}, B(rocks) non-zero={sum(1 for w in terrain_b_weights if w > 0.001)}")
assert sum(1 for w in terrain_r_weights if w > 0.001) > 0, "Terrain tree weights should be present"
assert sum(1 for w in terrain_b_weights if w > 0.001) > 0, "Terrain rock weights should be present"

print("\n=== 3. Simulating Engine LCG Pseudo-Random Rejection Sampling ===")
class LcgRng:
    def __init__(self, seed: int):
        self.state = seed & 0xFFFFFFFF
    def next_u32(self) -> int:
        self.state = (self.state * 1664525 + 1013904223) & 0xFFFFFFFF
        return self.state
    def next_f32(self) -> float:
        return (self.next_u32() >> 8) / 16777216.0

def read_vec3_accessor(acc_idx):
    acc = data["accessors"][acc_idx]
    bv = data["bufferViews"][acc["bufferView"]]
    offset = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    count = acc["count"]
    stride = bv.get("byteStride", 12)
    return [struct.unpack_from("<3f", bin_data, offset + i * stride) for i in range(count)]

def read_indices_accessor(acc_idx):
    acc = data["accessors"][acc_idx]
    bv = data["bufferViews"][acc["bufferView"]]
    offset = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    count = acc["count"]
    ctype = acc["componentType"]
    if ctype == 5123:
        stride = bv.get("byteStride", 2)
        return [struct.unpack_from("<H", bin_data, offset + i * stride)[0] for i in range(count)]
    elif ctype == 5125:
        stride = bv.get("byteStride", 4)
        return [struct.unpack_from("<I", bin_data, offset + i * stride)[0] for i in range(count)]

# Sample on road
road_positions = read_vec3_accessor(road_prim["attributes"]["POSITION"])
road_indices = read_indices_accessor(road_prim["indices"])
scale = road_node.get("scale", [1.0, 1.0, 1.0])[0]

tri_count = len(road_indices) // 3
cdf = []
running_sum = 0.0
for i in range(tri_count):
    i0, i1, i2 = road_indices[3*i], road_indices[3*i+1], road_indices[3*i+2]
    p0 = [c * scale for c in road_positions[i0]]
    p1 = [c * scale for c in road_positions[i1]]
    p2 = [c * scale for c in road_positions[i2]]
    v0 = (p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2])
    v1 = (p2[0]-p0[0], p2[1]-p0[1], p2[2]-p0[2])
    cross = (v0[1]*v1[2]-v0[2]*v1[1], v0[2]*v1[0]-v0[0]*v1[2], v0[0]*v1[1]-v0[1]*v1[0])
    area = 0.5 * math.sqrt(cross[0]**2 + cross[1]**2 + cross[2]**2)
    w0, w1, w2 = road_weights[i0], road_weights[i1], road_weights[i2]
    tri_w = area * ((w0 + w1 + w2) / 3.0) if max(w0, w1, w2) > 0.001 else 0.0
    running_sum += tri_w
    cdf.append(running_sum)

rng = LcgRng(1301)
road_instances = []
attempts = 0
target_count = 1200
while len(road_instances) < target_count and attempts < target_count * 10:
    attempts += 1
    target = rng.next_f32() * running_sum
    tri_idx = min(bisect.bisect_left(cdf, target), tri_count - 1)
    i0, i1, i2 = road_indices[3*tri_idx], road_indices[3*tri_idx+1], road_indices[3*tri_idx+2]
    w0, w1, w2 = road_weights[i0], road_weights[i1], road_weights[i2]
    r1, r2 = rng.next_f32(), rng.next_f32()
    sqrt_r1 = math.sqrt(r1)
    u = 1.0 - sqrt_r1
    v = r2 * sqrt_r1
    w = 1.0 - u - v
    pt_w = w0*u + w1*v + w2*w
    if pt_w <= 0.01 or rng.next_f32() > pt_w:
        continue
    p0 = [c * scale for c in road_positions[i0]]
    p1 = [c * scale for c in road_positions[i1]]
    p2 = [c * scale for c in road_positions[i2]]
    pos = (p0[0]*u + p1[0]*v + p2[0]*w, p0[1]*u + p1[1]*v + p2[1]*w, p0[2]*u + p1[2]*v + p2[2]*w)
    road_instances.append(pos)

print(f"Generated {len(road_instances)} road leaf instances in {attempts} attempts")
assert len(road_instances) == target_count, f"Expected {target_count} instances, got {len(road_instances)}"

road_radii = [math.sqrt(p[0]**2 + p[2]**2) for p in road_instances]
print(f"Road leaf world radii: min={min(road_radii):.2f}m, max={max(road_radii):.2f}m, avg={sum(road_radii)/len(road_radii):.2f}m")
assert min(road_radii) >= 41.5, f"Expected min radius >= 41.5m, got {min(road_radii):.2f}m"
assert max(road_radii) <= 48.0, f"Expected max radius <= 48.0m, got {max(road_radii):.2f}m"

# Sample against terrain leaf weights: must generate 0 instances
terrain_indices = read_indices_accessor(terrain_prim["indices"])
tri_count_t = len(terrain_indices) // 3
terrain_cdf_leaf = []
running_sum_t = 0.0
for i in range(tri_count_t):
    i0, i1, i2 = terrain_indices[3*i], terrain_indices[3*i+1], terrain_indices[3*i+2]
    w0, w1, w2 = terrain_leaf_weights[i0], terrain_leaf_weights[i1], terrain_leaf_weights[i2]
    tri_w = (w0 + w1 + w2) / 3.0 if max(w0, w1, w2) > 0.001 else 0.0
    running_sum_t += tri_w
    terrain_cdf_leaf.append(running_sum_t)

print(f"Terrain leaf scatter CDF running sum: {running_sum_t:.6f}")
assert running_sum_t <= 1e-6, "Terrain leaf scatter CDF running sum should be 0.0 (no leaves on terrain)!"

print("\nALL VERIFICATION CHECKS PASSED PERFECTLY!")
