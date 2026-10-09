// #region GltfLoader
use std::path::Path;
use glam::Mat4;
use wgpu::util::DeviceExt;

use crate::material::Material;
use crate::transform::compute_normal_matrix;

#[repr(C)]
#[derive(Copy, Clone, Debug, bytemuck::Pod, bytemuck::Zeroable)]
pub struct ObjectUniforms {
    pub model: [[f32; 4]; 4],
    pub normal_matrix: [[f32; 4]; 4],
}

pub struct GpuPrimitive {
    pub pos_buffer: wgpu::Buffer,
    pub norm_buffer: wgpu::Buffer,
    pub uv_buffer: wgpu::Buffer,
    pub index_buffer: Option<wgpu::Buffer>,
    pub count: u32,
    pub material_index: usize,
}

pub struct RenderNode {
    pub world_transform: Mat4,
    pub uniform_buffer: wgpu::Buffer,
    pub bind_group: wgpu::BindGroup,
    pub mesh_index: usize,
}

pub struct GltfScene {
    pub primitives_by_mesh: Vec<Vec<GpuPrimitive>>,
    pub materials: Vec<Material>,
    pub render_nodes: Vec<RenderNode>,
}

impl GltfScene {
    fn create_buffer(device: &wgpu::Device, label: &str, data: &[u8], usage: wgpu::BufferUsages) -> wgpu::Buffer {
        device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some(label),
            contents: data,
            usage,
        })
    }

    pub fn load<P: AsRef<Path>>(
        path: P,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        bgl_obj: &wgpu::BindGroupLayout,
        bgl_mat: &wgpu::BindGroupLayout,
        default_view: &wgpu::TextureView,
        default_sampler: &wgpu::Sampler,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        let path = path.as_ref();
        let base = path.parent().unwrap_or_else(|| Path::new("."));
        let reader = std::io::BufReader::new(std::fs::File::open(path)?);
        let gltf = gltf::Gltf::from_reader_without_validation(reader)?;
        let buffers = gltf::import_buffers(&gltf.document, Some(base), gltf.blob)?;
        let images = gltf::import_images(&gltf.document, Some(base), &buffers)?;
        let doc = gltf.document;
        println!("[GltfLoader-Load] Loaded glTF: {}", path.display());

        // 1. Process decoded images into RGBA8 buffers
        let processed_images: Vec<(Vec<u8>, u32, u32)> = images
            .into_iter()
            .map(|img| {
                let rgba = match img.format {
                    gltf::image::Format::R8G8B8A8 => img.pixels,
                    gltf::image::Format::R8G8B8 => {
                        img.pixels.chunks_exact(3).flat_map(|c| [c[0], c[1], c[2], 255]).collect()
                    }
                    _ => img.pixels.iter().flat_map(|&b| [b, b, b, 255]).collect(),
                };
                (rgba, img.width, img.height)
            })
            .collect();

        // 2. Initialize Materials
        let mut materials: Vec<_> = doc
            .materials()
            .map(|mat| {
                let pbr = mat.pbr_metallic_roughness();
                let base_color = pbr.base_color_factor();
                let is_transparent = mat.alpha_mode() != gltf::material::AlphaMode::Opaque || base_color[3] < 0.99;
                let texture_data = pbr.base_color_texture().and_then(|info| {
                    let (bytes, w, h) = &processed_images[info.texture().source().index()];
                    Some((bytes.as_slice(), *w, *h))
                });
                Material::new(
                    device, queue, bgl_mat, default_view, default_sampler,
                    base_color, pbr.metallic_factor(), pbr.roughness_factor(),
                    is_transparent, texture_data,
                )
            })
            .collect();

        if materials.is_empty() {
            materials.push(Material::new(
                device, queue, bgl_mat, default_view, default_sampler,
                [1.0, 1.0, 1.0, 1.0], 0.0, 0.5, false, None,
            ));
        }

        // 3. Initialize GPU Primitives per Mesh
        let primitives_by_mesh: Vec<Vec<GpuPrimitive>> = doc
            .meshes()
            .map(|mesh| {
                mesh.primitives()
                    .filter_map(|prim| {
                        let reader = prim.reader(|b| Some(&buffers[b.index()]));
                        let positions: Vec<[f32; 3]> = reader.read_positions()?.collect();
                        let normals: Vec<[f32; 3]> = reader
                            .read_normals()
                            .map(|n| n.collect())
                            .unwrap_or_else(|| vec![[0.0, 1.0, 0.0]; positions.len()]);
                        let uvs: Vec<[f32; 2]> = reader
                            .read_tex_coords(0)
                            .map(|tc| tc.into_f32().collect())
                            .unwrap_or_else(|| vec![[0.0, 0.0]; positions.len()]);
                        let indices: Option<Vec<u32>> = reader.read_indices().map(|i| i.into_u32().collect());
                        let count = indices.as_ref().map_or(positions.len() as u32, |i| i.len() as u32);

                        Some(GpuPrimitive {
                            pos_buffer: Self::create_buffer(device, "Pos", bytemuck::cast_slice(&positions), wgpu::BufferUsages::VERTEX),
                            norm_buffer: Self::create_buffer(device, "Norm", bytemuck::cast_slice(&normals), wgpu::BufferUsages::VERTEX),
                            uv_buffer: Self::create_buffer(device, "UV", bytemuck::cast_slice(&uvs), wgpu::BufferUsages::VERTEX),
                            index_buffer: indices.as_ref().map(|idx| {
                                Self::create_buffer(device, "Idx", bytemuck::cast_slice(idx), wgpu::BufferUsages::INDEX)
                            }),
                            count,
                            material_index: prim.material().index().unwrap_or(0).min(materials.len() - 1),
                        })
                    })
                    .collect()
            })
            .collect();

        // 4. Traverse Node Hierarchy to build RenderNodes iteratively
        let mut render_nodes = Vec::new();
        let mut stack: Vec<(gltf::Node, Mat4)> = doc
            .default_scene()
            .map_or_else(|| doc.nodes().collect::<Vec<_>>(), |s| s.nodes().collect())
            .into_iter()
            .map(|n| (n, Mat4::IDENTITY))
            .collect();

        while let Some((node, parent_transform)) = stack.pop() {
            let world_transform = parent_transform * Mat4::from_cols_array_2d(&node.transform().matrix());

            if let Some(mesh) = node.mesh() {
                let uniforms = ObjectUniforms {
                    model: world_transform.to_cols_array_2d(),
                    normal_matrix: compute_normal_matrix(world_transform).to_cols_array_2d(),
                };
                let uniform_buffer = Self::create_buffer(device, "ObjectUniform", bytemuck::bytes_of(&uniforms), wgpu::BufferUsages::UNIFORM);
                let bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
                    label: Some("Object BindGroup"),
                    layout: bgl_obj,
                    entries: &[wgpu::BindGroupEntry {
                        binding: 0,
                        resource: uniform_buffer.as_entire_binding(),
                    }],
                });

                render_nodes.push(RenderNode {
                    world_transform,
                    uniform_buffer,
                    bind_group,
                    mesh_index: mesh.index(),
                });
            }

            for child in node.children() {
                stack.push((child, world_transform));
            }
        }

        println!(
            "[GltfLoader-Init] Loaded {} meshes, {} materials, {} render instances.",
            primitives_by_mesh.len(),
            materials.len(),
            render_nodes.len()
        );

        Ok(Self {
            primitives_by_mesh,
            materials,
            render_nodes,
        })
    }
}
// #endregion
