// #region Imports
use std::borrow::Cow;
use std::collections::{HashMap, HashSet};
use std::path::Path;

use glam::{Mat3, Mat4, Vec3};
use wgpu::util::DeviceExt;

use crate::material::Material;
// #endregion

// #region Types
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
    pub center: Vec3,
}

pub struct RenderNode {
    pub world_transform: Mat4,
    pub uniform_buffer: wgpu::Buffer,
    pub bind_group: wgpu::BindGroup,
    pub mesh_index: usize,
}

pub struct SceneCamera {
    pub name: Option<String>,
    pub world_transform: Mat4,
    pub yfov: f32,
    pub znear: f32,
    pub zfar: Option<f32>,
}

pub struct SceneLight {
    pub name: Option<String>,
    pub direction: Vec3,
    pub color: [f32; 3],
    pub intensity: f32,
}

pub struct GltfScene {
    pub primitives_by_mesh: Vec<Vec<GpuPrimitive>>,
    pub materials: Vec<Material>,
    pub render_nodes: Vec<RenderNode>,
    pub camera: SceneCamera,
    pub light: SceneLight,
}

struct TextureData {
    rgba: Vec<u8>,
    width: u32,
    height: u32,
}
// #endregion

// #region Scaffolding
impl SceneCamera {
    pub fn view_matrix(&self) -> Mat4 {
        self.world_transform.inverse()
    }

    pub fn position(&self) -> Vec3 {
        self.world_transform.transform_point3(Vec3::ZERO)
    }

    pub fn projection_matrix(&self, aspect: f32) -> Mat4 {
        if let Some(far) = self.zfar {
            Mat4::perspective_rh(self.yfov, aspect, self.znear, far)
        } else {
            Mat4::perspective_infinite_rh(self.yfov, aspect, self.znear)
        }
    }
}

impl GltfScene {
    fn create_buffer(device: &wgpu::Device, label: &str, data: &[u8], usage: wgpu::BufferUsages) -> wgpu::Buffer {
        device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some(label),
            contents: data,
            usage,
        })
    }

    fn image_bytes<'a>(
        image: &gltf::Image,
        buffers: &'a [gltf::buffer::Data],
        base: &Path,
    ) -> Option<Cow<'a, [u8]>> {
        match image.source() {
            gltf::image::Source::View { view, .. } => {
                let buffer = view.buffer();
                let data: &'a [u8] = &buffers[buffer.index()];
                let start = view.offset();
                let end = start + view.length();
                data.get(start..end).map(Cow::Borrowed)
            }
            gltf::image::Source::Uri { uri, .. } => {
                if uri.starts_with("data:") {
                    crate::telemetry::log_warn("GltfLoader", "Texture", &format!("Unsupported data URI image: {uri}"));
                    None
                } else {
                    std::fs::read(base.join(uri)).ok().map(Cow::Owned)
                }
            }
        }
    }

    fn decode_texture(bytes: &[u8], max_texture_size: u32) -> Result<TextureData, Box<dyn std::error::Error>> {
        let decoded = image::load_from_memory(bytes)?.to_rgba8();
        let (width, height) = decoded.dimensions();
        let longest = width.max(height);

        if max_texture_size > 0 && longest > max_texture_size {
            let scale = max_texture_size as f32 / longest as f32;
            let new_width = ((width as f32 * scale).round() as u32).max(1);
            let new_height = ((height as f32 * scale).round() as u32).max(1);
            let resized = image::imageops::resize(
                &decoded,
                new_width,
                new_height,
                image::imageops::FilterType::Lanczos3,
            );
            Ok(TextureData {
                rgba: resized.into_raw(),
                width: new_width,
                height: new_height,
            })
        } else {
            Ok(TextureData { rgba: decoded.into_raw(), width, height })
        }
    }

    fn load_textures(
        doc: &gltf::Document,
        buffers: &[gltf::buffer::Data],
        base: &Path,
        max_texture_size: u32,
    ) -> HashMap<usize, TextureData> {
        let needed: HashSet<usize> = doc
            .materials()
            .filter_map(|mat| {
                mat.pbr_metallic_roughness()
                    .base_color_texture()
                    .map(|info| info.texture().source().index())
            })
            .collect();
        let images: Vec<gltf::Image> = doc.images().collect();
        let mut textures = HashMap::new();

        for index in needed {
            let Some(image) = images.get(index) else {
                crate::telemetry::log_warn("GltfLoader", "Texture", &format!("Missing image index {index}"));
                continue;
            };
            let Some(bytes) = Self::image_bytes(image, buffers, base) else {
                crate::telemetry::log_warn("GltfLoader", "Texture", &format!("Unreadable image '{}'", image.name().unwrap_or("unnamed")));
                continue;
            };
            let decode_start = std::time::Instant::now();
            match Self::decode_texture(&bytes, max_texture_size) {
                Ok(texture) => {
                    crate::telemetry::log_info("GltfLoader", "Texture", &format!(
                        "{} decoded to {}x{} in {:?}",
                        image.name().unwrap_or("unnamed"), texture.width, texture.height, decode_start.elapsed()
                    ));
                    textures.insert(index, texture);
                }
                Err(error) => {
                    crate::telemetry::log_warn("GltfLoader", "Texture", &format!("Decode failed for '{}': {error:?}", image.name().unwrap_or("unnamed")));
                }
            }
        }

        textures
    }

    fn create_texture_view(device: &wgpu::Device, queue: &wgpu::Queue, data: &TextureData) -> wgpu::TextureView {
        let mip_level_count = 32 - data.width.max(data.height).leading_zeros();
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Material Texture"),
            size: wgpu::Extent3d {
                width: data.width,
                height: data.height,
                depth_or_array_layers: 1,
            },
            mip_level_count,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8UnormSrgb,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });

        let mut level = image::RgbaImage::from_raw(data.width, data.height, data.rgba.clone())
            .expect("valid RGBA texture dimensions");

        for mip_level in 0..mip_level_count {
            let (width, height) = level.dimensions();
            queue.write_texture(
                wgpu::ImageCopyTexture {
                    texture: &texture,
                    mip_level,
                    origin: wgpu::Origin3d::ZERO,
                    aspect: wgpu::TextureAspect::All,
                },
                level.as_raw(),
                wgpu::ImageDataLayout {
                    offset: 0,
                    bytes_per_row: Some(4 * width),
                    rows_per_image: Some(height),
                },
                wgpu::Extent3d {
                    width,
                    height,
                    depth_or_array_layers: 1,
                },
            );

            if mip_level + 1 < mip_level_count {
                let next = ((width / 2).max(1), (height / 2).max(1));
                level = image::imageops::resize(&level, next.0, next.1, image::imageops::FilterType::Triangle);
            }
        }

        texture.create_view(&wgpu::TextureViewDescriptor::default())
    }

    fn build_materials(
        doc: &gltf::Document,
        textures: &HashMap<usize, TextureData>,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        bgl_mat: &wgpu::BindGroupLayout,
        default_view: &wgpu::TextureView,
        default_sampler: &wgpu::Sampler,
    ) -> Vec<Material> {
        let mut texture_views: HashMap<usize, wgpu::TextureView> = HashMap::new();
        let mut materials = Vec::new();

        let root = doc.as_json();
        for mat in doc.materials() {
            let pbr = mat.pbr_metallic_roughness();
            let base_color = pbr.base_color_factor();
            let is_unlit = mat.unlit();
            let alpha_cutoff = mat.alpha_cutoff().unwrap_or(0.5);
            let alpha_mode = match mat.alpha_mode() {
                gltf::material::AlphaMode::Opaque => 0u32,
                gltf::material::AlphaMode::Mask => 1u32,
                gltf::material::AlphaMode::Blend => 2u32,
            };
            let is_transparent = mat.alpha_mode() == gltf::material::AlphaMode::Blend;
            let clearcoat = mat
                .index()
                .and_then(|idx| root.materials.get(idx))
                .and_then(|m| m.extensions.as_ref())
                .and_then(|ext| ext.others.get("KHR_materials_clearcoat"))
                .and_then(|val| val.get("clearcoatFactor"))
                .and_then(|cf| cf.as_f64())
                .map(|f| f as f32)
                .unwrap_or(0.0);
            let texture_index = pbr
                .base_color_texture()
                .map(|info| info.texture().source().index());
            let texture_view = texture_index.and_then(|index| {
                textures.get(&index).map(|data| {
                    let view = texture_views
                        .entry(index)
                        .or_insert_with(|| Self::create_texture_view(device, queue, data));
                    &*view
                })
            });

            materials.push(Material::new(
                device,
                bgl_mat,
                default_view,
                default_sampler,
                texture_view,
                base_color,
                pbr.metallic_factor(),
                pbr.roughness_factor(),
                clearcoat,
                alpha_cutoff,
                alpha_mode,
                is_unlit,
                is_transparent,
                mat.double_sided(),
            ));
        }

        if materials.is_empty() {
            materials.push(Material::new(
                device,
                bgl_mat,
                default_view,
                default_sampler,
                None,
                [1.0, 1.0, 1.0, 1.0],
                0.0,
                0.5,
                0.0,
                0.5,
                0,
                false,
                false,
                false,
            ));
        }
        materials
    }

    fn build_primitives(
        doc: &gltf::Document,
        buffers: &[gltf::buffer::Data],
        materials_len: usize,
        device: &wgpu::Device,
    ) -> (Vec<Vec<GpuPrimitive>>, Vec<(Vec3, Vec3)>) {
        let built: Vec<(Vec<GpuPrimitive>, (Vec3, Vec3))> = doc
            .meshes()
            .map(|mesh| {
                let mut mesh_min = Vec3::splat(f32::MAX);
                let mut mesh_max = Vec3::splat(f32::MIN);

                let primitives: Vec<GpuPrimitive> = mesh
                    .primitives()
                    .filter_map(|prim| {
                        let reader = prim.reader(|b| Some(&buffers[b.index()]));
                        let positions: Vec<[f32; 3]> = reader.read_positions()?.collect();

                        let mut prim_min = Vec3::splat(f32::MAX);
                        let mut prim_max = Vec3::splat(f32::MIN);
                        for p in &positions {
                            let v = Vec3::from_slice(p);
                            prim_min = prim_min.min(v);
                            prim_max = prim_max.max(v);
                        }
                        mesh_min = mesh_min.min(prim_min);
                        mesh_max = mesh_max.max(prim_max);

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
                        let center = if positions.is_empty() {
                            Vec3::ZERO
                        } else {
                            (prim_min + prim_max) * 0.5
                        };

                        Some(GpuPrimitive {
                            pos_buffer: Self::create_buffer(device, "Pos", bytemuck::cast_slice(&positions), wgpu::BufferUsages::VERTEX),
                            norm_buffer: Self::create_buffer(device, "Norm", bytemuck::cast_slice(&normals), wgpu::BufferUsages::VERTEX),
                            uv_buffer: Self::create_buffer(device, "UV", bytemuck::cast_slice(&uvs), wgpu::BufferUsages::VERTEX),
                            index_buffer: indices.as_ref().map(|idx| {
                                Self::create_buffer(device, "Idx", bytemuck::cast_slice(idx), wgpu::BufferUsages::INDEX)
                            }),
                            count,
                            material_index: prim.material().index().unwrap_or(0).min(materials_len - 1),
                            center,
                        })
                    })
                    .collect();

                let bounds = if mesh_min.x <= mesh_max.x {
                    (mesh_min, mesh_max)
                } else {
                    (Vec3::ZERO, Vec3::ZERO)
                };
                (primitives, bounds)
            })
            .collect();

        let mut primitives_by_mesh = Vec::with_capacity(built.len());
        let mut mesh_bounds = Vec::with_capacity(built.len());
        for (primitives, bounds) in built {
            primitives_by_mesh.push(primitives);
            mesh_bounds.push(bounds);
        }
        (primitives_by_mesh, mesh_bounds)
    }

    fn expand_bounds(min: Vec3, max: Vec3, transform: &Mat4, bounds_min: &mut Vec3, bounds_max: &mut Vec3) {
        for corner in 0..8 {
            let point = Vec3::new(
                if corner & 1 == 0 { min.x } else { max.x },
                if corner & 2 == 0 { min.y } else { max.y },
                if corner & 4 == 0 { min.z } else { max.z },
            );
            let world = transform.transform_point3(point);
            *bounds_min = bounds_min.min(world);
            *bounds_max = bounds_max.max(world);
        }
    }

    fn build_render_nodes(
        doc: &gltf::Document,
        device: &wgpu::Device,
        bgl_obj: &wgpu::BindGroupLayout,
        mesh_bounds: &[(Vec3, Vec3)],
    ) -> (Vec<RenderNode>, Vec<SceneCamera>, Vec<SceneLight>, (Vec3, Vec3)) {
        let mut render_nodes = Vec::new();
        let mut cameras = Vec::new();
        let mut lights = Vec::new();
        let mut bounds_min = Vec3::splat(f32::MAX);
        let mut bounds_max = Vec3::splat(f32::MIN);

        let mut stack: Vec<(gltf::Node, Mat4)> = doc
            .default_scene()
            .map_or_else(|| doc.nodes().collect::<Vec<_>>(), |s| s.nodes().collect())
            .into_iter()
            .map(|n| (n, Mat4::IDENTITY))
            .collect();

        while let Some((node, parent_transform)) = stack.pop() {
            let world_transform = parent_transform * Mat4::from_cols_array_2d(&node.transform().matrix());

            if let Some(mesh) = node.mesh() {
                let normal_matrix = Mat4::from_mat3(Mat3::from_mat4(world_transform).inverse().transpose());
                let uniforms = ObjectUniforms {
                    model: world_transform.to_cols_array_2d(),
                    normal_matrix: normal_matrix.to_cols_array_2d(),
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

                if let Some(&(min, max)) = mesh_bounds.get(mesh.index()) {
                    Self::expand_bounds(min, max, &world_transform, &mut bounds_min, &mut bounds_max);
                }
            }

            if let Some(cam) = node.camera() {
                let (yfov, znear, zfar) = match cam.projection() {
                    gltf::camera::Projection::Perspective(p) => (p.yfov(), p.znear(), p.zfar()),
                    gltf::camera::Projection::Orthographic(o) => (o.ymag(), o.znear(), Some(o.zfar())),
                };
                cameras.push(SceneCamera {
                    name: cam.name().map(String::from).or_else(|| node.name().map(String::from)),
                    world_transform,
                    yfov,
                    znear,
                    zfar,
                });
            }

            if let Some(light) = node.light() {
                let toward_light = world_transform.transform_vector3(Vec3::Z);
                let direction = if toward_light.length_squared() > 1e-6 {
                    toward_light.normalize()
                } else {
                    Vec3::Y
                };
                lights.push(SceneLight {
                    name: light.name().map(String::from).or_else(|| node.name().map(String::from)),
                    direction,
                    color: light.color(),
                    intensity: light.intensity(),
                });
            }

            for child in node.children() {
                stack.push((child, world_transform));
            }
        }

        let bounds = if bounds_min.x <= bounds_max.x {
            (bounds_min, bounds_max)
        } else {
            (Vec3::splat(-1.0), Vec3::splat(1.0))
        };
        (render_nodes, cameras, lights, bounds)
    }

    fn create_fallback_camera(bounds: &(Vec3, Vec3)) -> SceneCamera {
        let center = (bounds.0 + bounds.1) * 0.5;
        let extents = bounds.1 - bounds.0;
        let radius = extents.length().max(1.0);
        let eye = center + Vec3::new(0.0, radius * 0.5, radius * 1.8);
        let view = Mat4::look_at_rh(eye, center, Vec3::Y);
        SceneCamera {
            name: Some("AutoFramingFallbackCamera".to_string()),
            world_transform: view.inverse(),
            yfov: 45.0f32.to_radians(),
            znear: 0.1,
            zfar: Some(radius * 10.0),
        }
    }

    fn enforce_single_camera_policy(mut cameras: Vec<SceneCamera>, bounds: &(Vec3, Vec3)) -> SceneCamera {
        if cameras.len() == 1 {
            let cam = cameras.remove(0);
            crate::telemetry::log_info("GltfLoader", "Camera", &format!("Policy Verified: Exactly 1 camera found in glTF: '{}'", cam.name.as_deref().unwrap_or("unnamed")));
            cam
        } else if cameras.is_empty() {
            crate::telemetry::log_warn("GltfLoader", "Camera", "Policy Violation: 0 cameras found in glTF file. Generating auto-framing fallback camera.");
            Self::create_fallback_camera(bounds)
        } else {
            crate::telemetry::log_warn("GltfLoader", "Camera", &format!("Policy Violation: {} cameras found in glTF file. Enforcing single active camera rule using first camera.", cameras.len()));
            cameras.remove(0)
        }
    }

    fn resolve_active_light(lights: Vec<SceneLight>) -> SceneLight {
        if let Some(light) = lights.into_iter().next() {
            crate::telemetry::log_info("GltfLoader", "Light", &format!("Active glTF Light: '{}' (dir: [{:.2}, {:.2}, {:.2}], intensity: {:.0})", light.name.as_deref().unwrap_or("unnamed"), light.direction.x, light.direction.y, light.direction.z, light.intensity));
            light
        } else {
            crate::telemetry::log_info("GltfLoader", "Light", "No light in glTF file. Using default sun vector.");
            SceneLight {
                name: Some("DefaultSun".to_string()),
                direction: Vec3::new(0.5, 1.0, -0.6).normalize(),
                color: [1.0, 1.0, 1.0],
                intensity: 1000.0,
            }
        }
    }
}
// #endregion

// #region Core
impl GltfScene {
    #[allow(clippy::too_many_arguments)]
    pub fn load<P: AsRef<Path>>(
        path: P,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        bgl_obj: &wgpu::BindGroupLayout,
        bgl_mat: &wgpu::BindGroupLayout,
        default_view: &wgpu::TextureView,
        default_sampler: &wgpu::Sampler,
        max_texture_size: u32,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        let path = path.as_ref();
        let base = path.parent().unwrap_or_else(|| Path::new("."));
        let start = std::time::Instant::now();
        let gltf = gltf::Gltf::from_reader_without_validation(std::io::BufReader::new(std::fs::File::open(path)?))?;
        let buffers = gltf::import_buffers(&gltf.document, Some(base), gltf.blob)?;
        crate::telemetry::log_info("GltfLoader", "Load", &format!("Reading glTF scene: {} ({:.1} MB imported in {:?})", path.display(), buffers.iter().map(|buffer| buffer.len()).sum::<usize>() as f64 / 1048576.0, start.elapsed()));

        let textures = Self::load_textures(&gltf.document, &buffers, base, max_texture_size);
        let decoded = start.elapsed();
        let materials = Self::build_materials(&gltf.document, &textures, device, queue, bgl_mat, default_view, default_sampler);
        let uploaded = start.elapsed();
        drop(textures);
        let (primitives_by_mesh, mesh_bounds) = Self::build_primitives(&gltf.document, &buffers, materials.len(), device);
        let built_primitives = start.elapsed();
        let (render_nodes, cameras, lights, bounds) = Self::build_render_nodes(&gltf.document, device, bgl_obj, &mesh_bounds);
        let camera = Self::enforce_single_camera_policy(cameras, &bounds);
        let light = Self::resolve_active_light(lights);
        let built_nodes = start.elapsed();

        crate::telemetry::log_info("GltfLoader", "Init", &format!(
            "Loaded {} meshes, {} materials, {} instances (decode: {decoded:?}, upload: {:?}, primitives: {:?}, nodes: {:?}, total: {:?}).",
            primitives_by_mesh.len(), materials.len(), render_nodes.len(),
            uploaded - decoded, built_primitives - uploaded, built_nodes - built_primitives, start.elapsed()
        ));
        Ok(Self { primitives_by_mesh, materials, render_nodes, camera, light })
    }
}
// #endregion
