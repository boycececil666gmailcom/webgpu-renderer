#!/usr/bin/env python3
#region Imports
import os
import sys
import glob
import json
import struct
import io
from pathlib import Path
from PIL import Image
#endregion

#region Types
# Pre-baked binary mipmap texture cache:
# Magic: b"MIP0" (4 bytes)
# base_w (u32), base_h (u32), mip_count (u32)
# Repeated for each mip:
#   mip_w (u32), mip_h (u32), byte_len (u32), raw_rgba_bytes (byte_len bytes)
#endregion

#region Scaffolding
MAX_MIP_LEVELS = 8
MAGIC = b"MIP0"

def fnv1a_64(data: bytes) -> int:
    h = 0xcbf29ce484222325
    for b in data:
        h ^= b
        h = (h * 0x100000001b3) & 0xffffffffffffffff
    return h

def compute_mip_count(w: int, h: int, max_levels: int = MAX_MIP_LEVELS) -> int:
    dim = max(w, h)
    levels = dim.bit_length()
    return max(1, min(levels, max_levels))
#endregion

#region Domain
def bake_image_to_mips(raw_bytes: bytes, out_path: str) -> bool:
    if os.path.exists(out_path) and os.path.getsize(out_path) > 16:
        return False

    im = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
    base_w, base_h = im.size
    mip_count = compute_mip_count(base_w, base_h)

    mips_data = []
    current_im = im
    for level in range(mip_count):
        w, h = current_im.size
        raw_pixels = current_im.tobytes()
        mips_data.append((w, h, raw_pixels))

        if level + 1 < mip_count:
            next_w = max(1, w // 2)
            next_h = max(1, h // 2)
            current_im = current_im.resize((next_w, next_h), Image.Resampling.BILINEAR)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<III", base_w, base_h, mip_count))
        for w, h, pixels in mips_data:
            f.write(struct.pack("<III", w, h, len(pixels)))
            f.write(pixels)

    return True

def process_glb_file(glb_path: str, cache_dir: str) -> tuple[int, int]:
    new_baked = 0
    skipped = 0
    with open(glb_path, "rb") as f:
        header = f.read(12)
        if len(header) < 12 or header[:4] != b"glTF":
            return (0, 0)
        chunk_len, chunk_type = struct.unpack("<I4s", f.read(8))
        if chunk_type != b"JSON":
            return (0, 0)
        json_bytes = f.read(chunk_len)
        bin_len, bin_type = struct.unpack("<I4s", f.read(8))
        if bin_type != b"BIN\x00":
            return (0, 0)
        bin_data = f.read(bin_len)

    json_doc = json.loads(json_bytes)
    bvs = json_doc.get("bufferViews", [])
    images = json_doc.get("images", [])

    for img in images:
        if "bufferView" not in img:
            continue
        bv = bvs[img["bufferView"]]
        offset = bv.get("byteOffset", 0)
        length = bv["byteLength"]
        raw = bin_data[offset:offset + length]
        h_hex = f"{fnv1a_64(raw):016x}"
        out_file = os.path.join(cache_dir, f"{h_hex}.mips")
        if bake_image_to_mips(raw, out_file):
            new_baked += 1
        else:
            skipped += 1

    return (new_baked, skipped)

def process_external_image(img_path: str, cache_dir: str) -> bool:
    with open(img_path, "rb") as f:
        raw = f.read()
    h_hex = f"{fnv1a_64(raw):016x}"
    out_file = os.path.join(cache_dir, f"{h_hex}.mips")
    return bake_image_to_mips(raw, out_file)
#endregion

#region Core
def run_baking_pipeline(root_dir: str):
    models_dir = os.path.join(root_dir, "assets", "models")
    cache_dir = os.path.join(root_dir, "assets", "cache")
    os.makedirs(cache_dir, exist_ok=True)

    print(f"[BAKE-MIPS] Scanning GLB files in {models_dir}...")
    total_baked = 0
    total_skipped = 0

    glb_files = sorted(glob.glob(os.path.join(models_dir, "*.glb")))
    if not glb_files:
        # Fallback to assets/ root if not in models/
        glb_files = sorted(glob.glob(os.path.join(root_dir, "assets", "*.glb")))

    for glb_file in glb_files:
        name = os.path.basename(glb_file)
        baked, skipped = process_glb_file(glb_file, cache_dir)
        total_baked += baked
        total_skipped += skipped
        print(f"  - {name}: {baked} baked, {skipped} already cached")

    # External textures
    ext_tex = os.path.join(root_dir, "assets", "textures", "autumn_forest_01_1k.png")
    if os.path.isfile(ext_tex):
        if process_external_image(ext_tex, cache_dir):
            total_baked += 1
            print(f"  - autumn_forest_01_1k.png: 1 baked")
        else:
            total_skipped += 1
            print(f"  - autumn_forest_01_1k.png: 1 already cached")

    print(f"[BAKE-MIPS] Completed: {total_baked} baked, {total_skipped} reused. Cache directory: {cache_dir}")
#endregion

#region Main
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    run_baking_pipeline(project_root)
#endregion

