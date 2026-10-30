#!/usr/bin/env python3
#region Imports
import os
import sys
from dataclasses import dataclass
from typing import List, Tuple
from PIL import Image
#endregion

#region Types
@dataclass(frozen=True)
class LeafTextureSpec:
    name: str
    diffuse_filename: str
    opacity_filename: str
    target_filename: str
    target_dimensions: Tuple[int, int]
#endregion

#region Scaffolding
@dataclass(frozen=True)
class PipelineConfig:
    raw_dir: str
    output_dir: str
    specs: List[LeafTextureSpec]

def create_default_config() -> PipelineConfig:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    textures_dir = os.path.join(base_dir, "textures")
    raw_dir = os.path.join(textures_dir, "raw_leaf")
    
    specs = [
        LeafTextureSpec(
            name="Dry Leaves 01",
            diffuse_filename="Ever_cabins_4197 diff.jpg",
            opacity_filename="Ever_cabins_4197 opacity.jpg",
            target_filename="dry_leaves_01_rgba.png",
            target_dimensions=(1024, 1024)
        ),
        LeafTextureSpec(
            name="Dry Leaves 02",
            diffuse_filename="Ever_cabins_4232 diffuse.jpg",
            opacity_filename="Ever_cabins_4232 opacity.jpg",
            target_filename="dry_leaves_02_rgba.png",
            target_dimensions=(1024, 512)
        ),
        LeafTextureSpec(
            name="Dry Leaves 03",
            diffuse_filename="Ever_cabins_4208 diffuse.jpg",
            opacity_filename="Ever_cabins_4208 opacity2.jpg",
            target_filename="dry_leaves_03_rgba.png",
            target_dimensions=(1024, 1024)
        )
    ]
    return PipelineConfig(raw_dir=raw_dir, output_dir=textures_dir, specs=specs)
#endregion

#region Transform
def compose_rgba_leaf(spec: LeafTextureSpec, raw_dir: str, output_dir: str) -> str:
    diff_path = os.path.join(raw_dir, spec.diffuse_filename)
    opac_path = os.path.join(raw_dir, spec.opacity_filename)
    out_path = os.path.join(output_dir, spec.target_filename)
    
    with Image.open(diff_path) as diff_img, Image.open(opac_path) as opac_img:
        diff_rgb = diff_img.convert("RGB")
        opac_l = opac_img.convert("L")
        
        if diff_rgb.size != opac_l.size:
            opac_l = opac_l.resize(diff_rgb.size, Image.Resampling.BILINEAR)
            
        r, g, b = diff_rgb.split()
        rgba_img = Image.merge("RGBA", (r, g, b, opac_l))
        
        if rgba_img.size != spec.target_dimensions:
            rgba_img = rgba_img.resize(spec.target_dimensions, Image.Resampling.LANCZOS)
            
        rgba_img.save(out_path, format="PNG", optimize=True)
        print(f"[LeafTexturePipeline] Composed {spec.target_filename}: {rgba_img.size} ({os.path.getsize(out_path)} bytes)")
        
    return out_path
#endregion

#region Core
def run_leaf_texture_pipeline(config: PipelineConfig) -> List[str]:
    os.makedirs(config.output_dir, exist_ok=True)
    results = [compose_rgba_leaf(spec, config.raw_dir, config.output_dir) for spec in config.specs]
    return results
#endregion

#region Main
def main() -> int:
    config = create_default_config()
    run_leaf_texture_pipeline(config)
    return 0

if __name__ == "__main__":
    sys.exit(main())
#endregion

