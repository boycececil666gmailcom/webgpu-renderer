# region Imports
import os
import sys
import time

import wgpu

IS_ANDROID = "ANDROID_ARGUMENT" in os.environ

if IS_ANDROID:
    import ctypes
    import sdl2
    from sdl2 import syswm
    import wgpu.backends.wgpu_native._helpers as _helpers
    import wgpu.backends.wgpu_native._api as _api
    from wgpu.backends.wgpu_native._ffi import ffi, lib
    from wgpu.backends.wgpu_native._helpers import get_wgpu_instance
    from wgpu.backends.wgpu_native._api import GPUCanvasContext
else:
    import glfw
    from rendercanvas.glfw import RenderCanvas
# endregion


# region Surface
if IS_ANDROID:
    _orig_get_surface_id = _helpers.get_surface_id_from_info

    def _android_get_surface_id(present_info):
        if isinstance(present_info, dict) and present_info.get("platform") == "android":
            struct = ffi.new("WGPUSurfaceSourceAndroidNativeWindow *")
            struct.chain.sType = lib.WGPUSType_SurfaceSourceAndroidNativeWindow
            struct.window = ffi.cast("void *", present_info["window"])

            surface_descriptor = ffi.new("WGPUSurfaceDescriptor *")
            surface_descriptor.label.data = ffi.NULL
            surface_descriptor.nextInChain = ffi.cast("WGPUChainedStruct *", struct)

            return lib.wgpuInstanceCreateSurface(get_wgpu_instance(), surface_descriptor)
        return _orig_get_surface_id(present_info)

    _helpers.get_surface_id_from_info = _android_get_surface_id
    _api.get_surface_id_from_info = _android_get_surface_id
# endregion


# region Window
class Window:
    """Minimal WebGPU window abstraction for desktop (GLFW) and mobile (Android NDK)."""

    def __init__(self, width: int, height: int, title: str):
        self.width = width
        self.height = height
        self._should_close = False
        self.context = None

        if IS_ANDROID:
            self.canvas = None
            self._event = sdl2.SDL_Event()
            libsdl2 = ctypes.CDLL("libSDL2.so")
            libsdl2.Android_JNI_GetNativeWindow.restype = ctypes.c_void_p
            libsdl2.Android_JNI_GetNativeWindow.argtypes = []

            self.native_window = None
            for _ in range(50):
                ptr = libsdl2.Android_JNI_GetNativeWindow()
                if ptr:
                    self.native_window = ptr
                    break
                time.sleep(0.05)

            if not self.native_window:
                raise RuntimeError("Failed to acquire valid ANativeWindow from SDLActivity")

            libandroid = ctypes.CDLL("libandroid.so")
            libandroid.ANativeWindow_getWidth.restype = ctypes.c_int32
            libandroid.ANativeWindow_getWidth.argtypes = [ctypes.c_void_p]
            libandroid.ANativeWindow_getHeight.restype = ctypes.c_int32
            libandroid.ANativeWindow_getHeight.argtypes = [ctypes.c_void_p]

            w = libandroid.ANativeWindow_getWidth(self.native_window)
            h = libandroid.ANativeWindow_getHeight(self.native_window)
            if w > 0 and h > 0:
                self.width = w
                self.height = h

            print(
                f"[Window-Init] Android native surface acquired: {self.width}x{self.height}, handle={self.native_window}",
                flush=True,
            )
        else:
            self.canvas = RenderCanvas(size=(width, height), title=title)
            glfw.show_window(self.canvas._window)
            glfw.focus_window(self.canvas._window)

        self._init_wgpu()

    def _init_wgpu(self) -> None:
        print("[Window-Init] Requesting WebGPU adapter...", flush=True)
        self.adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
        if not self.adapter:
            raise RuntimeError("Failed to request WebGPU adapter")
        print(f"[Window-Init] Adapter acquired: {self.adapter}", flush=True)
        self.device = self.adapter.request_device_sync()
        print(f"[Window-Init] Device acquired: {self.device}", flush=True)

        if IS_ANDROID:
            present_info = {"platform": "android", "window": self.native_window}
            self.context = GPUCanvasContext(present_info)
            self.context.set_physical_size(self.width, self.height)
            caps = self.context._get_capabilities(self.adapter)
            formats = caps.get("formats", [])
            self.texture_format = formats[0] if formats else wgpu.TextureFormat.rgba8unorm
            alpha_modes = caps.get("alpha_modes", [])
            alpha_mode = "opaque" if "opaque" in alpha_modes else (alpha_modes[0] if alpha_modes else "inherit")
            print(
                f"[Window-Init] Configuring surface: format={self.texture_format}, alpha={alpha_mode}, size={self.width}x{self.height}",
                flush=True,
            )
            self.context.configure(
                device=self.device,
                format=self.texture_format,
                usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
                alpha_mode=alpha_mode,
            )
            print("[Window-Init] WebGPU swapchain configured successfully!", flush=True)
        else:
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
                print(f"[Window-Event] Event: {self._event.type}", flush=True)
                if self._event.type == sdl2.SDL_QUIT:
                    print("[Window-Event] SDL_QUIT received", flush=True)
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
            pass
        elif self.canvas:
            self.canvas.close()
            glfw.terminate()
# endregion
