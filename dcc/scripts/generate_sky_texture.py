#region Imports
import math
from PIL import Image
#endregion

#region Types
# Sky gradient generator
#endregion

#region Scaffolding
import random

def create_sky_gradient(width=2048, height=1024, out_path="c:/Users/boyce/OneDrive/Desktop/webgpu-renderer/Model/textures/sky_dome_gradient.png"):
    img = Image.new("RGBA", (width, height))
    pixels = img.load()

    # Precompute seamless 2D grid noise for realistic cumulus cloud banks
    grid_w, grid_h = 64, 32
    random.seed(42)
    grid = [[random.random() for _ in range(grid_w)] for _ in range(grid_h)]

    def smooth_step(val):
        return val * val * (3.0 - 2.0 * val)

    def sample_noise(gx, gy):
        x0 = int(math.floor(gx)) % grid_w
        x1 = (x0 + 1) % grid_w
        fx = smooth_step(gx - math.floor(gx))
        y0 = max(0, min(grid_h - 1, int(math.floor(gy))))
        y1 = max(0, min(grid_h - 1, y0 + 1))
        fy = smooth_step(gy - math.floor(gy))
        top = grid[y0][x0] * (1.0 - fx) + grid[y0][x1] * fx
        bot = grid[y1][x0] * (1.0 - fx) + grid[y1][x1] * fx
        return top * (1.0 - fy) + bot * fy

    def fbm(x_norm, y_norm):
        val = 0.0
        amp = 0.55
        freq_x = 8.0
        freq_y = 6.0
        for _ in range(4):
            val += sample_noise(x_norm * freq_x, y_norm * freq_y) * amp
            freq_x *= 2.0
            freq_y *= 2.0
            amp *= 0.5
        return val

    # Clean atmospheric palette without harsh white horizontal bands
    c_zenith = (15, 75, 185)       # Z = +60m (t=0.0): Deep rich blue
    c_upper = (45, 120, 215)       # Z = +40m (t=0.28): Azure blue
    c_mid = (85, 155, 230)         # Z = +20m (t=0.57): Clear sky blue
    c_lower = (135, 185, 235)      # Z = +5m (t=0.78): Atmospheric sky blue
    c_horizon = (175, 205, 228)    # Z = 0m (t=0.857): Soft desaturated pale sky (NO white stripe)
    c_terrain = (115, 125, 130)    # Z = -2m (t=0.89): Distant terrain haze fade
    c_base = (50, 55, 58)          # Z = -10m (t=1.0): Hidden cylinder base

    t_horizon = 60.0 / 70.0 # ~0.857

    sun_x = int(width * 0.42)
    sun_y = int(height * 0.25) # Sun high in the sky (Z ≈ +42m)

    for y in range(height):
        t = y / (height - 1.0) # 0.0 (top, Z=+60m) to 1.0 (bottom, Z=-10m)

        if t < 0.28:
            f = t / 0.28
            base = [c_zenith[i] + (c_upper[i] - c_zenith[i]) * f for i in range(3)]
        elif t < 0.57:
            f = (t - 0.28) / (0.57 - 0.28)
            base = [c_upper[i] + (c_mid[i] - c_upper[i]) * f for i in range(3)]
        elif t < 0.78:
            f = (t - 0.57) / (0.78 - 0.57)
            base = [c_mid[i] + (c_lower[i] - c_mid[i]) * f for i in range(3)]
        elif t < t_horizon:
            f = (t - 0.78) / (t_horizon - 0.78)
            base = [c_lower[i] + (c_horizon[i] - c_lower[i]) * f for i in range(3)]
        elif t < 0.90:
            f = (t - t_horizon) / (0.90 - t_horizon)
            base = [c_horizon[i] + (c_terrain[i] - c_horizon[i]) * f for i in range(3)]
        else:
            f = (t - 0.90) / (1.0 - 0.90)
            base = [c_terrain[i] + (c_base[i] - c_terrain[i]) * f for i in range(3)]

        for x in range(width):
            # Soft directional solar glow in upper sky
            dx = (x - sun_x) / float(width)
            if dx > 0.5: dx -= 1.0
            if dx < -0.5: dx += 1.0
            dy = (y - sun_y) / float(height)
            dist = math.sqrt(dx * dx * 3.5 + dy * dy * 1.5)
            sun_halo = max(0.0, 1.0 - dist * 2.5) ** 3.0 * 55.0

            # Realistic cumulus clouds located STRICTLY in high sky (t in 0.10 to 0.45 -> Z = +28m to +53m)
            cloud_factor = 0.0
            if 0.10 < t < 0.45:
                x_norm = x / float(width)
                v = (t - 0.10) / (0.45 - 0.10)
                noise_val = fbm(x_norm, v)
                if noise_val > 0.48:
                    puff = (noise_val - 0.48) / 0.52
                    env = math.sin(v * math.pi) ** 1.4
                    cloud_factor = min(1.0, (puff * 1.6) ** 1.2 * env)

            c_cloud = (248, 250, 255)
            r = min(255, int((base[0] + sun_halo * 1.0) * (1.0 - cloud_factor) + c_cloud[0] * cloud_factor))
            g = min(255, int((base[1] + sun_halo * 0.92) * (1.0 - cloud_factor) + c_cloud[1] * cloud_factor))
            b = min(255, int((base[2] + sun_halo * 0.75) * (1.0 - cloud_factor) + c_cloud[2] * cloud_factor))
            pixels[x, y] = (r, g, b, 255)

    img.save(out_path, "PNG")
    print(f"[SKY] Generated calibrated realistic sky texture: {out_path} ({width}x{height})")
#endregion

#region Core
def run():
    create_sky_gradient()
#endregion

#region Main
if __name__ == '__main__':
    run()
#endregion

