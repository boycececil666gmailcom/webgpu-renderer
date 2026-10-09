#!/usr/bin/env python
# region Imports
import os
import sys
import time
import traceback

# Android runtime environment configuration
if "ANDROID_ARGUMENT" in os.environ or "ANDROID_BOOTLOGO" in os.environ:
    if "WGPU_LIB_PATH" not in os.environ:
        os.environ["WGPU_LIB_PATH"] = "libwgpu_native.so"

class _DiskLogger:
    def __init__(self):
        self._f = open("run.log", "w", buffering=1, encoding="utf-8")
        self._orig = sys.stdout

    def write(self, s):
        try:
            self._orig.write(s)
            self._orig.flush()
        except Exception:
            pass
        try:
            self._f.write(s)
            self._f.flush()
        except Exception:
            pass

    def flush(self):
        try:
            self._orig.flush()
            self._f.flush()
        except Exception:
            pass

_logger = _DiskLogger()
sys.stdout = _logger
sys.stderr = _logger

print("[Main-Init] TeeLogger initialized, starting application...", flush=True)

from pygltflib import GLTF2

from engine import Camera, Config, Renderer, Shader, Window
# endregion


# region Main Entrypoint
def main():
    # 1. Resolve 3D model glTF/GLB file path argument (with default fallback)
    if len(sys.argv) > 1:
        model_path = sys.argv[1]
    else:
        default_model = "gltf/mclaren_p1.glb"
        if os.path.exists(default_model):
            model_path = default_model
            print(f"[Main-Run] No model argument provided. Defaulting to '{model_path}'.")
        else:
            print("[Main-Run] Usage: python main.py <path_to_gltf_file>")
            sys.exit(1)

    if not os.path.exists(model_path):
        print(f"[Main-Run] Error: Model file '{model_path}' not found.")
        sys.exit(1)

    # 2. Load configuration and initialize context
    config = Config()
    window = Window(
        config.scr_width,
        config.scr_height,
        "Antigravity WebGPU Engine",
    )
    renderer = Renderer(window, config)

    # 3. Load native glTF 2.0 file, shaders, and camera
    shader = Shader("shaders/shader.wgsl")
    gltf = GLTF2.load(model_path)
    base_dir = os.path.dirname(model_path)

    camera = Camera(
        pos=config.cam_pos,
        target=config.cam_target,
        fov=config.cam_fov,
        near=config.cam_near,
        far=config.cam_far,
    )

    print(f"[Main-Run] Loaded Native glTF 2.0: {model_path}", flush=True)
    print(f"[Main-Run] Target Frame Rate: {config.target_fps} FPS", flush=True)

    # 4. Main Rendering Loop
    try:
        while not window.should_close():
            frame_start = time.time()

            window.process_input()
            renderer.render_frame(shader, gltf, camera, base_dir)
            renderer.limit_frame_rate(frame_start)
    finally:
        # 5. Clean up allocated graphics card buffers
        renderer.clean_cache(gltf)
        shader.delete()
        window.terminate()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        err = traceback.format_exc()
        print(f"[Main-Fatal] Unhandled exception: {err}", flush=True)
        try:
            with open("crash_trace.log", "w", encoding="utf-8") as f:
                f.write(err)
        except Exception:
            pass
        sys.exit(1)
# endregion
