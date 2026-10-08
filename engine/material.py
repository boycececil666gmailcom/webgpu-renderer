import io
import os
import struct

import numpy as np
import wgpu
from PIL import Image
from pygltflib import Material as GLTFMaterial

# endregion


# region Material Class
class Material(GLTFMaterial):
    """WebGPU PBR Material extending pygltflib.Material."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gpu_texture = None
        self.texture_view = None
        self.sampler = None
        self.uniform_buffer = None
        self._bind_group = None
        self.has_texture = False

    @property
    def base_color_vec4(self) -> np.ndarray:
        pbr = self.pbrMetallicRoughness
        if pbr and pbr.baseColorFactor:
            c = pbr.baseColorFactor
            return np.array([c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0], dtype=np.float32)
        return np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)

    @property
    def metallic_val(self) -> float:
        pbr = self.pbrMetallicRoughness
        return float(pbr.metallicFactor) if pbr and pbr.metallicFactor is not None else 0.0

    @property
    def roughness_val(self) -> float:
        pbr = self.pbrMetallicRoughness
        return float(pbr.roughnessFactor) if pbr and pbr.roughnessFactor is not None else 0.5

    @property
    def is_transparent(self) -> bool:
        return self.alphaMode in ["BLEND", "MASK"] or self.base_color_vec4.a < 0.99

    def load_texture(self, device: wgpu.GPUDevice, img_source) -> None:
        """Loads and uploads an image into a WebGPU texture."""
        try:
            if isinstance(img_source, (str, os.PathLike)):
                pil_img = Image.open(img_source)
            elif isinstance(img_source, (bytes, io.BytesIO)):
                stream = io.BytesIO(img_source) if isinstance(img_source, bytes) else img_source
                pil_img = Image.open(stream)
            else:
                pil_img = img_source

            if pil_img.mode != "RGBA":
                pil_img = pil_img.convert("RGBA")

            width, height = pil_img.size
            img_data = np.ascontiguousarray(np.array(pil_img, dtype=np.uint8))

            self.gpu_texture = device.create_texture(
                size=(width, height, 1),
                format=wgpu.TextureFormat.rgba8unorm_srgb,
                usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
            )
            device.queue.write_texture(
                destination={"texture": self.gpu_texture},
                data=img_data.tobytes(),
                data_layout={"bytes_per_row": width * 4, "rows_per_image": height},
                size=(width, height, 1),
            )
            self.texture_view = self.gpu_texture.create_view()
            self.sampler = device.create_sampler(
                address_mode_u=wgpu.AddressMode.repeat,
                address_mode_v=wgpu.AddressMode.repeat,
                min_filter=wgpu.FilterMode.linear,
                mag_filter=wgpu.FilterMode.linear,
            )
            self.has_texture = True
        except Exception as e:
            print(f"[Material-Load] Error loading texture: {e}")
            self.has_texture = False

    def get_bind_group(
        self,
        device: wgpu.GPUDevice,
        layout: wgpu.GPUBindGroupLayout,
        default_view: wgpu.GPUTextureView,
        default_sampler: wgpu.GPUSampler,
    ) -> wgpu.GPUBindGroup:
        """Retrieves or lazily instantiates the WebGPU material bind group."""
        if self._bind_group is None:
            col = self.base_color_vec4
            raw_uniforms = struct.pack(
                "<4f2f2I",
                float(col[0]),
                float(col[1]),
                float(col[2]),
                float(col[3]),
                self.metallic_val,
                self.roughness_val,
                1 if self.has_texture else 0,
                0,
            )
            self.uniform_buffer = device.create_buffer_with_data(
                data=raw_uniforms,
                usage=wgpu.BufferUsage.UNIFORM,
            )
            view = self.texture_view if self.has_texture and self.texture_view else default_view
            sampler = self.sampler if self.has_texture and self.sampler else default_sampler

            self._bind_group = device.create_bind_group(
                layout=layout,
                entries=[
                    {
                        "binding": 0,
                        "resource": {"buffer": self.uniform_buffer, "offset": 0, "size": 32},
                    },
                    {"binding": 1, "resource": view},
                    {"binding": 2, "resource": sampler},
                ],
            )
        return self._bind_group

    def delete(self) -> None:
        """Releases GPU resources."""
        self.gpu_texture = None
        self.texture_view = None
        self.sampler = None
        self.uniform_buffer = None
        self._bind_group = None


# endregion
