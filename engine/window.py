# region Imports
import sys

import glfw
import wgpu
from rendercanvas.glfw import RenderCanvas

# endregion


# region Window Backend
class Window:
    """Window and WebGPU context abstraction powered by wgpu-py and GLFW."""

    def __init__(self, width: int, height: int, title: str):
        self.width = width
        self.height = height

        # Initialize RenderCanvas (GLFW backend)
        self.canvas = RenderCanvas(size=(width, height), title=title)
        self.handle = self.canvas._window

        # Initialize WebGPU Adapter and Device
        self.adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
        if not self.adapter:
            print("[Window-Init] Error: Failed to acquire WebGPU adapter.")
            sys.exit(1)

        self.device = self.adapter.request_device_sync()
        if not self.device:
            print("[Window-Init] Error: Failed to create WebGPU device.")
            sys.exit(1)

        # Configure WebGPU Canvas Context
        self.context = self.canvas.get_wgpu_context()
        self.texture_format = self.context.get_preferred_format(self.adapter)
        self.context.configure(device=self.device, format=self.texture_format)

        # Log active graphics pipeline details
        print(f"[Window-Init] WebGPU Adapter: {self.adapter.summary}")
        print(f"[Window-Init] WebGPU Swapchain Format: {self.texture_format}")

        # Explicitly reveal and focus window on desktop
        glfw.show_window(self.handle)
        glfw.focus_window(self.handle)

    def should_close(self) -> bool:
        return glfw.window_should_close(self.handle)

    def swap_buffers(self) -> None:
        self.context._wgpu_context.present()

    def poll_events(self) -> None:
        glfw.poll_events()

    def process_input(self) -> None:
        if glfw.get_key(self.handle, glfw.KEY_ESCAPE) == glfw.PRESS:
            glfw.set_window_should_close(self.handle, True)

    def get_size(self) -> tuple[int, int]:
        return self.canvas.get_physical_size()

    def get_aspect(self) -> float:
        w, h = self.get_size()
        return w / h if h > 0 else 1.0

    def terminate(self) -> None:
        self.canvas.close()
        glfw.terminate()


# endregion
