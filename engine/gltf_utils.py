import io
import os

import numpy as np
import wgpu
from pygltflib import GLTF2

from engine.material import Material
from engine.transform import compose_transform, normal_matrix

# endregion


# region Component Mappings
COMPONENT_TYPES = {
    5120: np.int8,
    5121: np.uint8,
    5122: np.int16,
    5123: np.uint16,
    5125: np.uint32,
    5126: np.float32,
}

TYPE_ELEMENTS = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}
# endregion


# region Buffer Extraction
def get_buffer_data(gltf: GLTF2, buffer_idx: int, base_dir: str = ".") -> bytes:
    """Extracts raw bytes from a glTF buffer reference (binary blob, base64, or file)."""
    buffer = gltf.buffers[buffer_idx]
    if not buffer.uri:
        return gltf.binary_blob()
    if buffer.uri.startswith("data:"):
        return gltf.get_data_from_buffer_uri(buffer.uri)
    bin_path = os.path.join(base_dir, buffer.uri)
    if os.path.exists(bin_path):
        with open(bin_path, "rb") as f:
            return f.read()
    return gltf.get_data_from_buffer_uri(buffer.uri)


def extract_accessor_data(gltf: GLTF2, accessor_idx: int, base_dir: str = ".") -> np.ndarray | None:
    """Decodes glTF accessor data into a formatted numpy ndarray."""
    if accessor_idx is None or accessor_idx < 0:
        return None

    accessor = gltf.accessors[accessor_idx]
    if accessor.bufferView is None:
        return None

    buffer_view = gltf.bufferViews[accessor.bufferView]
    raw_buffer_data = get_buffer_data(gltf, buffer_view.buffer, base_dir)

    byte_offset = (buffer_view.byteOffset or 0) + (accessor.byteOffset or 0)
    dtype = COMPONENT_TYPES.get(accessor.componentType, np.float32)
    num_elements = TYPE_ELEMENTS.get(accessor.type, 1)

    elem_size = np.dtype(dtype).itemsize
    total_elements = accessor.count * num_elements
    total_bytes = total_elements * elem_size

    buffer_slice = raw_buffer_data[byte_offset : byte_offset + total_bytes]
    arr = np.frombuffer(buffer_slice, dtype=dtype)
    return arr.reshape((accessor.count, num_elements)) if num_elements > 1 else arr


def get_node_transform_matrix(node) -> np.ndarray:
    """Build local transformation matrix (4x4 float32 ndarray) for a glTF Node."""
    if hasattr(node, "matrix") and node.matrix and len(node.matrix) == 16:
        return np.array(node.matrix, dtype=np.float32).reshape((4, 4)).T

    return compose_transform(
        translation=getattr(node, "translation", None),
        rotation=getattr(node, "rotation", None),
        scale=getattr(node, "scale", None),
    )


# endregion


# region Buffer Cache
class GLTFBufferCache:
    """Manages WebGPU vertex, index, uniform, and texture buffers for a glTF scene."""

    def __init__(
        self,
        gltf: GLTF2,
        device: wgpu.GPUDevice,
        base_dir: str = ".",
        bgl_obj: wgpu.GPUBindGroupLayout = None,
        bgl_mat: wgpu.GPUBindGroupLayout = None,
        default_view: wgpu.GPUTextureView = None,
        default_sampler: wgpu.GPUSampler = None,
    ):
        self.gltf = gltf
        self.device = device
        self.base_dir = base_dir
        self.bgl_obj = bgl_obj
        self.bgl_mat = bgl_mat
        self.default_view = default_view
        self.default_sampler = default_sampler

        self.materials: list[Material] = []
        self.gpu_primitives: dict = {}
        self.node_cache: dict[int, dict] = {}

        self._init_materials()
        self._init_gpu_buffers()
        self._init_node_hierarchy()

    def _init_materials(self) -> None:
        if not self.gltf.materials:
            return

        for mat_data in self.gltf.materials:
            mat = Material.from_dict(mat_data.to_dict())
            pbr = getattr(mat, "pbrMetallicRoughness", None)
            if pbr and getattr(pbr, "baseColorTexture", None):
                tex_idx = pbr.baseColorTexture.index
                if self.gltf.textures and tex_idx < len(self.gltf.textures):
                    img_idx = self.gltf.textures[tex_idx].source
                    if self.gltf.images and img_idx < len(self.gltf.images):
                        img_info = self.gltf.images[img_idx]
                        if img_info.bufferView is not None:
                            bv = self.gltf.bufferViews[img_info.bufferView]
                            raw_blob = get_buffer_data(self.gltf, bv.buffer, self.base_dir)
                            offset = bv.byteOffset or 0
                            img_bytes = raw_blob[offset : offset + bv.byteLength]
                            mat.load_texture(self.device, io.BytesIO(img_bytes))
                        elif img_info.uri:
                            if img_info.uri.startswith("data:"):
                                mat.load_texture(
                                    self.device,
                                    self.gltf.get_data_from_buffer_uri(img_info.uri),
                                )
                            else:
                                img_path = os.path.join(self.base_dir, img_info.uri)
                                if os.path.exists(img_path):
                                    mat.load_texture(self.device, img_path)

            # Pre-create material bind group
            if self.bgl_mat:
                mat.get_bind_group(
                    self.device,
                    self.bgl_mat,
                    self.default_view,
                    self.default_sampler,
                )
            self.materials.append(mat)

    def _init_gpu_buffers(self) -> None:
        if not self.gltf.meshes:
            return

        for mesh_idx, mesh in enumerate(self.gltf.meshes):
            for prim_idx, primitive in enumerate(mesh.primitives):
                positions = extract_accessor_data(
                    self.gltf, primitive.attributes.POSITION, self.base_dir
                )
                if positions is None or len(positions) == 0:
                    continue

                count = len(positions)
                normals = extract_accessor_data(
                    self.gltf, primitive.attributes.NORMAL, self.base_dir
                )
                if normals is None or len(normals) == 0:
                    normals = np.zeros((count, 3), dtype=np.float32)

                uvs = extract_accessor_data(
                    self.gltf, primitive.attributes.TEXCOORD_0, self.base_dir
                )
                if uvs is None or len(uvs) == 0:
                    uvs = np.zeros((count, 2), dtype=np.float32)

                indices = extract_accessor_data(self.gltf, primitive.indices, self.base_dir)

                mat = (
                    self.materials[primitive.material]
                    if primitive.material is not None and primitive.material < len(self.materials)
                    else Material()
                )

                has_indices = indices is not None and len(indices) > 0
                draw_count = len(indices.reshape(-1)) if has_indices else count

                # Upload vertex buffers to WebGPU
                pos_arr = np.ascontiguousarray(positions, dtype=np.float32)
                norm_arr = np.ascontiguousarray(normals, dtype=np.float32)
                uv_arr = np.ascontiguousarray(uvs, dtype=np.float32)

                buf_pos = self.device.create_buffer_with_data(
                    data=pos_arr, usage=wgpu.BufferUsage.VERTEX
                )
                buf_norm = self.device.create_buffer_with_data(
                    data=norm_arr, usage=wgpu.BufferUsage.VERTEX
                )
                buf_uv = self.device.create_buffer_with_data(
                    data=uv_arr, usage=wgpu.BufferUsage.VERTEX
                )

                buf_idx = None
                if has_indices:
                    idx_arr = np.ascontiguousarray(indices.reshape(-1), dtype=np.uint32)
                    buf_idx = self.device.create_buffer_with_data(
                        data=idx_arr, usage=wgpu.BufferUsage.INDEX
                    )

                self.gpu_primitives[(mesh_idx, prim_idx)] = {
                    "buf_pos": buf_pos,
                    "buf_norm": buf_norm,
                    "buf_uv": buf_uv,
                    "buf_idx": buf_idx,
                    "has_indices": has_indices,
                    "count": draw_count,
                    "material": mat,
                }

    def _init_node_hierarchy(self) -> None:
        if not self.gltf.nodes or not self.bgl_obj:
            return

        scene_nodes = (
            self.gltf.scenes[self.gltf.scene or 0].nodes
            if self.gltf.scenes
            else list(range(len(self.gltf.nodes)))
        ) or []

        for root_idx in scene_nodes:
            self._traverse_node(root_idx, np.eye(4, dtype=np.float32))

    def _traverse_node(self, node_idx: int, parent_transform: np.ndarray) -> None:
        node = self.gltf.nodes[node_idx]
        world_transform = parent_transform @ get_node_transform_matrix(node)

        # Calculate normal matrix: transpose(inverse(world_transform[:3, :3]))
        norm_mat = normal_matrix(world_transform)

        model_bytes = world_transform.T.tobytes()
        norm_bytes = norm_mat.T.tobytes()

        buf = self.device.create_buffer_with_data(
            data=model_bytes + norm_bytes,
            usage=wgpu.BufferUsage.UNIFORM,
        )
        bind_group = self.device.create_bind_group(
            layout=self.bgl_obj,
            entries=[{"binding": 0, "resource": {"buffer": buf, "offset": 0, "size": 128}}],
        )

        self.node_cache[node_idx] = {
            "world": world_transform,
            "buffer": buf,
            "bind_group": bind_group,
        }

        for child_idx in getattr(node, "children", []) or []:
            self._traverse_node(child_idx, world_transform)

    def delete(self) -> None:
        """Cleans up all cached WebGPU resources."""
        self.gpu_primitives.clear()
        self.node_cache.clear()
        for mat in self.materials:
            mat.delete()
        self.materials.clear()


# endregion
