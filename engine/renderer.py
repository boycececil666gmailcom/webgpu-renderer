# region Imports
import struct
import time

import numpy as np
import wgpu
from pygltflib import GLTF2

from engine.camera import Camera
from engine.config import Config
from engine.gltf_utils import GLTFBufferCache
from engine.shader import Shader
from engine.window import Window

# endregion


# region Renderer Class
class Renderer:
    """glTF 2.0 WebGPU Renderer powered by wgpu-py."""

    def __init__(self, window: Window, config: Config):
        self.window = window
        self.config = config
        self.device = window.device
        self.clear_color = (0.094, 0.094, 0.106, 1.0)
        self._buffer_caches: dict[int, GLTFBufferCache] = {}

        self.depth_texture = None
        self.depth_view = None
        self._depth_size = (0, 0)

        self._init_shared_resources()
        self._init_layouts()
        self.pipeline_opaque = None
        self.pipeline_transparent = None

    def _init_shared_resources(self) -> None:
        # Default 1x1 white texture for untextured materials
        self.default_texture = self.device.create_texture(
            size=(1, 1, 1),
            format=wgpu.TextureFormat.rgba8unorm_srgb,
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        )
        self.device.queue.write_texture(
            destination={"texture": self.default_texture},
            data=b"\xff\xff\xff\xff",
            data_layout={"bytes_per_row": 4, "rows_per_image": 1},
            size=(1, 1, 1),
        )
        self.default_view = self.default_texture.create_view()
        self.default_sampler = self.device.create_sampler(
            address_mode_u=wgpu.AddressMode.repeat,
            address_mode_v=wgpu.AddressMode.repeat,
            min_filter=wgpu.FilterMode.linear,
            mag_filter=wgpu.FilterMode.linear,
        )

        # Frame Uniform Buffer (144 bytes: view 64B, projection 64B, light_dir 12B, pad 4B)
        self.frame_buffer = self.device.create_buffer(
            size=144,
            usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
        )

    def _init_layouts(self) -> None:
        self.bgl_frame = self.device.create_bind_group_layout(
            entries=[
                {
                    "binding": 0,
                    "visibility": wgpu.ShaderStage.VERTEX | wgpu.ShaderStage.FRAGMENT,
                    "buffer": {"type": wgpu.BufferBindingType.uniform},
                }
            ]
        )
        self.bgl_obj = self.device.create_bind_group_layout(
            entries=[
                {
                    "binding": 0,
                    "visibility": wgpu.ShaderStage.VERTEX,
                    "buffer": {"type": wgpu.BufferBindingType.uniform},
                }
            ]
        )
        self.bgl_mat = self.device.create_bind_group_layout(
            entries=[
                {
                    "binding": 0,
                    "visibility": wgpu.ShaderStage.FRAGMENT,
                    "buffer": {"type": wgpu.BufferBindingType.uniform},
                },
                {
                    "binding": 1,
                    "visibility": wgpu.ShaderStage.FRAGMENT,
                    "texture": {
                        "sample_type": wgpu.TextureSampleType.float,
                        "view_dimension": wgpu.TextureViewDimension.d2,
                    },
                },
                {
                    "binding": 2,
                    "visibility": wgpu.ShaderStage.FRAGMENT,
                    "sampler": {"type": wgpu.SamplerBindingType.filtering},
                },
            ]
        )
        self.pipeline_layout = self.device.create_pipeline_layout(
            bind_group_layouts=[self.bgl_frame, self.bgl_obj, self.bgl_mat]
        )
        self.frame_bind_group = self.device.create_bind_group(
            layout=self.bgl_frame,
            entries=[
                {
                    "binding": 0,
                    "resource": {"buffer": self.frame_buffer, "offset": 0, "size": 144},
                }
            ],
        )

    def _init_pipelines(self, shader_module: wgpu.GPUShaderModule) -> None:
        vertex_buffers = [
            {
                "array_stride": 12,
                "step_mode": wgpu.VertexStepMode.vertex,
                "attributes": [
                    {"format": wgpu.VertexFormat.float32x3, "offset": 0, "shader_location": 0}
                ],
            },
            {
                "array_stride": 12,
                "step_mode": wgpu.VertexStepMode.vertex,
                "attributes": [
                    {"format": wgpu.VertexFormat.float32x3, "offset": 0, "shader_location": 1}
                ],
            },
            {
                "array_stride": 8,
                "step_mode": wgpu.VertexStepMode.vertex,
                "attributes": [
                    {"format": wgpu.VertexFormat.float32x2, "offset": 0, "shader_location": 2}
                ],
            },
        ]

        blend_state = {
            "color": {
                "src_factor": wgpu.BlendFactor.src_alpha,
                "dst_factor": wgpu.BlendFactor.one_minus_src_alpha,
                "operation": wgpu.BlendOperation.add,
            },
            "alpha": {
                "src_factor": wgpu.BlendFactor.one,
                "dst_factor": wgpu.BlendFactor.one_minus_src_alpha,
                "operation": wgpu.BlendOperation.add,
            },
        }

        self.pipeline_opaque = self.device.create_render_pipeline(
            layout=self.pipeline_layout,
            vertex={"module": shader_module, "entry_point": "vs_main", "buffers": vertex_buffers},
            fragment={
                "module": shader_module,
                "entry_point": "fs_main",
                "targets": [{"format": self.window.texture_format, "blend": blend_state}],
            },
            primitive={
                "topology": wgpu.PrimitiveTopology.triangle_list,
                "cull_mode": wgpu.CullMode.none,
            },
            depth_stencil={
                "format": wgpu.TextureFormat.depth24plus,
                "depth_write_enabled": True,
                "depth_compare": wgpu.CompareFunction.less,
            },
        )

        self.pipeline_transparent = self.device.create_render_pipeline(
            layout=self.pipeline_layout,
            vertex={"module": shader_module, "entry_point": "vs_main", "buffers": vertex_buffers},
            fragment={
                "module": shader_module,
                "entry_point": "fs_main",
                "targets": [{"format": self.window.texture_format, "blend": blend_state}],
            },
            primitive={
                "topology": wgpu.PrimitiveTopology.triangle_list,
                "cull_mode": wgpu.CullMode.none,
            },
            depth_stencil={
                "format": wgpu.TextureFormat.depth24plus,
                "depth_write_enabled": False,
                "depth_compare": wgpu.CompareFunction.less,
            },
        )

    def _ensure_depth_texture(self, width: int, height: int) -> None:
        if self.depth_texture is None or self._depth_size != (width, height):
            width = max(width, 1)
            height = max(height, 1)
            self.depth_texture = self.device.create_texture(
                size=(width, height, 1),
                format=wgpu.TextureFormat.depth24plus,
                usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
            )
            self.depth_view = self.depth_texture.create_view()
            self._depth_size = (width, height)

    def render_frame(
        self, shader: Shader, gltf: GLTF2, camera: Camera, base_dir: str = "."
    ) -> None:
        """Executes a single render frame pass directly from a pygltflib.GLTF2 instance."""
        if self.pipeline_opaque is None:
            self._init_pipelines(shader.get_module(self.device))

        gltf_id = id(gltf)
        if gltf_id not in self._buffer_caches:
            self._buffer_caches[gltf_id] = GLTFBufferCache(
                gltf=gltf,
                device=self.device,
                base_dir=base_dir,
                bgl_obj=self.bgl_obj,
                bgl_mat=self.bgl_mat,
                default_view=self.default_view,
                default_sampler=self.default_sampler,
            )
        cache = self._buffer_caches[gltf_id]

        # Update Frame Uniforms (View, Projection, LightDir)
        view_mat = camera.get_view_matrix().T.tobytes()
        proj_mat = camera.get_projection_matrix(self.window.get_aspect()).T.tobytes()
        ld = self.config.light_dir
        light_bytes = struct.pack(
            "<4f",
            float(ld[0]),
            float(ld[1]),
            float(ld[2]),
            0.0,
        )
        self.device.queue.write_buffer(self.frame_buffer, 0, view_mat + proj_mat + light_bytes)

        # Acquire swapchain texture & match depth texture
        current_texture = self.window.context.get_current_texture()
        w, h = self.window.get_size()
        self._ensure_depth_texture(w, h)

        encoder = self.device.create_command_encoder()
        render_pass = encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": current_texture.create_view(),
                    "resolve_target": None,
                    "clear_value": self.clear_color,
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
            ],
            depth_stencil_attachment={
                "view": self.depth_view,
                "depth_clear_value": 1.0,
                "depth_load_op": wgpu.LoadOp.clear,
                "depth_store_op": wgpu.StoreOp.store,
            },
        )

        render_pass.set_bind_group(0, self.frame_bind_group)

        # Two-pass rendering: Pass 1 Opaque, Pass 2 Transparent
        for is_transparent in (False, True):
            render_pass.set_pipeline(
                self.pipeline_transparent if is_transparent else self.pipeline_opaque
            )
            for node_idx, node_info in cache.node_cache.items():
                node = gltf.nodes[node_idx]
                if node.mesh is not None and node.mesh < len(gltf.meshes):
                    render_pass.set_bind_group(1, node_info["bind_group"])
                    for prim_idx in range(len(gltf.meshes[node.mesh].primitives)):
                        prim = cache.gpu_primitives.get((node.mesh, prim_idx))
                        if not prim:
                            continue

                        mat = prim["material"]
                        if mat.is_transparent != is_transparent:
                            continue

                        mat_bg = mat.get_bind_group(
                            self.device,
                            self.bgl_mat,
                            self.default_view,
                            self.default_sampler,
                        )
                        render_pass.set_bind_group(2, mat_bg)
                        render_pass.set_vertex_buffer(0, prim["buf_pos"])
                        render_pass.set_vertex_buffer(1, prim["buf_norm"])
                        render_pass.set_vertex_buffer(2, prim["buf_uv"])

                        if prim["has_indices"]:
                            render_pass.set_index_buffer(prim["buf_idx"], wgpu.IndexFormat.uint32)
                            render_pass.draw_indexed(prim["count"])
                        else:
                            render_pass.draw(prim["count"])

        render_pass.end()
        self.device.queue.submit([encoder.finish()])

        self.window.swap_buffers()
        self.window.poll_events()

    def clean_cache(self, gltf: GLTF2 = None) -> None:
        """Cleans GPU buffer caches."""
        if gltf is not None:
            cache = self._buffer_caches.pop(id(gltf), None)
            if cache:
                cache.delete()
        else:
            for cache in self._buffer_caches.values():
                cache.delete()
            self._buffer_caches.clear()

    def limit_frame_rate(self, frame_start_time: float) -> None:
        """Applies software frame rate limiting based on Config settings."""
        if self.config.target_frame_time > 0:
            remaining = self.config.target_frame_time - (time.time() - frame_start_time)
            if remaining > 0:
                time.sleep(remaining)


# endregion
