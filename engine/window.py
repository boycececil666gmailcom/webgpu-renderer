# region Imports
import os
import sys

import wgpu

IS_ANDROID = "ANDROID_ARGUMENT" in os.environ

if IS_ANDROID:
    import ctypes
    import sdl2
else:
    import glfw
    from rendercanvas.glfw import RenderCanvas
# endregion


# region Window Backend
class Window:
    """Minimal WebGPU window abstraction for desktop (GLFW) and mobile (SDL2)."""

    def __init__(self, width: int, height: int, title: str):
        self.width = width
        self.height = height
        self._should_close = False
        self.context = None

        if IS_ANDROID:
            self.canvas = None
            self._event = sdl2.SDL_Event()
            sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_EVENTS)
        else:
            self.canvas = RenderCanvas(size=(width, height), title=title)
            glfw.show_window(self.canvas._window)
            glfw.focus_window(self.canvas._window)

        self._init_wgpu()

    def _init_wgpu(self) -> None:
        self.adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
        if not self.adapter:
            return
        self.device = self.adapter.request_device_sync()
        if self.canvas:
            self.context = self.canvas.get_wgpu_context()
            self.texture_format = self.context.get_preferred_format(self.adapter)
            self.context.configure(device=self.device, format=self.texture_format)

    def should_close(self) -> bool:
        if IS_ANDROID:
            return self._should_close
        return glfw.window_should_close(self.canvas._window)

    def poll_events(self) -> None:
        if IS_ANDROID:
            while sdl2.SDL_PollEvent(ctypes.byref(self._event)) != 0:
                if self._event.type == sdl2.SDL_QUIT:
                    self._should_close = True
        else:
            glfw.poll_events()

    def swap_buffers(self) -> None:
        if self.context and hasattr(self.context, "present"):
            self.context.present()

    def process_input(self) -> None:
        if not IS_ANDROID and glfw.get_key(self.canvas._window, glfw.KEY_ESCAPE) == glfw.PRESS:
            glfw.set_window_should_close(self.canvas._window, True)

    def get_size(self) -> tuple[int, int]:
        return self.canvas.get_physical_size() if self.canvas else (self.width, self.height)

    def get_aspect(self) -> float:
        w, h = self.get_size()
        return w / h if h > 0 else 1.0

    def terminate(self) -> None:
        if IS_ANDROID:
            sdl2.SDL_Quit()
        elif self.canvas:
            self.canvas.close()
            glfw.terminate()
# endregion
