import os
import numpy as np
from PIL import Image

def generate_luxury_metallic_flake_texture(
    output_path: str = r"c:\Users\boyce\OneDrive\Desktop\webgpu-renderer\Model\textures\metallic_red_paint_flake.png",
    width: int = 1024,
    height: int = 1024
):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    rng = np.random.RandomState(42)

    # Base Rosso Mars Candy Red in sRGB
    base_r = 212.0
    base_g = 10.0
    base_b = 8.0

    # Create base array
    r = np.full((height, width), base_r, dtype=np.float32)
    g = np.full((height, width), base_g, dtype=np.float32)
    b = np.full((height, width), base_b, dtype=np.float32)

    # 1. Subtle smooth depth variation (liquid candy lacquer depth)
    # Low frequency smooth noise
    x = np.linspace(0, 8 * np.pi, width)
    y = np.linspace(0, 8 * np.pi, height)
    xv, yv = np.meshgrid(x, y)
    swirl = (np.sin(xv) * np.cos(yv) + np.sin(2 * xv + yv) * 0.5) * 4.0
    r += swirl
    g += swirl * 0.05
    b += swirl * 0.05

    # 2. Suspended Aluminum & Mica Micro-Flakes (高精細マイカ・アルミラメ粒子)
    # Dense micro-flake field: 80,000 tiny microscopic flakes
    num_flakes = 120000
    fx = rng.randint(0, width, size=num_flakes)
    fy = rng.randint(0, height, size=num_flakes)
    
    # Flake intensities: metallic highlights that catch the light
    # Some flakes are ruby red, some are sparkling silver/gold flecks
    f_intensities = rng.uniform(25.0, 85.0, size=num_flakes)
    f_gold = rng.uniform(0.0, 1.0, size=num_flakes)

    for i in range(num_flakes):
        x_c, y_c = fx[i], fy[i]
        val = f_intensities[i]
        r[y_c, x_c] = min(255.0, r[y_c, x_c] + val)
        if f_gold[i] > 0.7: # 30% are pearlescent mica / golden flakes
            g[y_c, x_c] = min(120.0, g[y_c, x_c] + val * 0.35)
            b[y_c, x_c] = min(60.0, b[y_c, x_c] + val * 0.15)
        else: # 70% are deep candy red flakes
            g[y_c, x_c] = min(50.0, g[y_c, x_c] + val * 0.10)
            b[y_c, x_c] = min(40.0, b[y_c, x_c] + val * 0.08)

    # Clip to valid 8-bit range
    r = np.clip(r, 0, 255).astype(np.uint8)
    g = np.clip(g, 0, 255).astype(np.uint8)
    b = np.clip(b, 0, 255).astype(np.uint8)
    a = np.full((height, width), 255, dtype=np.uint8)

    rgba = np.stack([r, g, b, a], axis=-1)
    img = Image.fromarray(rgba, mode='RGBA')
    img.save(output_path, format='PNG', optimize=True)
    print(f"Generated luxury metallic flake texture at {output_path} ({os.path.getsize(output_path)} bytes)")

if __name__ == '__main__':
    generate_luxury_metallic_flake_texture()

