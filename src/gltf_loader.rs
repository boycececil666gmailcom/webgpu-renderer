// #region Imports
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use glam::{Mat3, Mat4, Vec3};
use image::GenericImageView;
use wgpu::util::DeviceExt;

use crate::material::Material;
// #endregion

// #region Types
#[repr(C)]
#[derive(Copy, Clone, Debug, bytemuck::Pod, bytemuck::Zeroable)]
pub struct InstanceRaw {
    pub model: [[f32; 4]; 4],
    pub normal_matrix: [[f32; 4]; 4],
}

impl InstanceRaw {
    pub fn from_transform(model: Mat4) -> Self {
        let normal_matrix = Mat4::from_mat3(Mat3::from_mat4(model).inverse().transpose());
        Self {
            model: model.to_cols_array_2d(),
            normal_matrix: normal_matrix.to_cols_array_2d(),
        }
    }
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
    pub name: Option<String>,
    pub world_transform: Mat4,
    pub instance_buffer: wgpu::Buffer,
    pub instance_count: u32,
    pub mesh_index: usize,
}

#[derive(Clone, Debug)]
pub struct RawPrimitiveData {
    pub positions: Vec<Vec3>,
    pub normals: Vec<Vec3>,
    pub indices: Vec<u32>,
    pub color0: Vec<[f32; 4]>,
    pub color1: Vec<[f32; 4]>,
}

#[derive(Clone, Debug)]
pub struct SurfaceData {
    pub name: String,
    pub positions: Vec<Vec3>,
    pub normals: Vec<Vec3>,
    pub indices: Vec<u32>,
    pub color0: Vec<[f32; 4]>,
    pub color1: Vec<[f32; 4]>,
    pub world_transform: Mat4,
}

fn default_true() -> bool { true }
fn default_channel() -> u32 { 1 }
fn default_component() -> String { "R".to_string() }

#[derive(Clone, Debug, serde::Deserialize)]
pub struct ScatterLodConfig {
    #[serde(default)]
    pub lod_level: u32,
    pub prototype_asset: String,
    #[serde(default)]
    pub min_screen_coverage_percent: f32,
}

fn default_radius() -> f32 { 0.09 }

#[derive(Clone, Debug, serde::Deserialize)]
pub struct ScatterRule {
    pub name: String,
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default)]
    pub prototype_asset: Option<String>,
    pub target_surface_node: String,
    #[serde(default = "default_channel")]
    pub weight_channel: u32,
    #[serde(default = "default_component")]
    pub weight_component: String,
    pub count: usize,
    pub seed: u64,
    pub scale_min: f32,
    pub scale_max: f32,
    pub normal_offset: f32,
    #[serde(default = "default_true")]
    pub yaw_random: bool,
    #[serde(default = "default_radius")]
    pub bounding_sphere_radius: f32,
    #[serde(default)]
    pub cull_screen_coverage_percent: f32,
    #[serde(default)]
    pub lods: Vec<ScatterLodConfig>,
}

#[derive(Clone, Debug)]
pub struct ScatterInstanceItem {
    pub transform: InstanceRaw,
    pub position: Vec3,
    pub world_radius: f32,
}

pub struct ScatterLodLevel {
    pub mesh_index: usize,
    pub render_node_index: usize,
    pub min_screen_coverage_percent: f32,
}

pub struct ScatterLodGroup {
    pub name: String,
    pub instances: Vec<ScatterInstanceItem>,
    pub lods: Vec<ScatterLodLevel>,
    pub cull_screen_coverage_percent: f32,
    pub last_eval_cam: Option<(Vec3, f32, f32)>,
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
    pub scatter_groups: Vec<ScatterLodGroup>,
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

    fn downsample_image(img: image::DynamicImage, max_size: u32) -> (Vec<u8>, u32, u32) {
        let (w, h) = img.dimensions();
        let scaled = if w > max_size || h > max_size {
            let aspect = w as f32 / h as f32;
            let (target_w, target_h) = if w > h {
                (max_size, (max_size as f32 / aspect).round() as u32)
            } else {
                ((max_size as f32 * aspect).round() as u32, max_size)
            };
            img.resize(target_w.max(1), target_h.max(1), image::imageops::FilterType::Triangle)
        } else {
            img
        };
        let (nw, nh) = scaled.dimensions();
        (scaled.to_rgba8().into_raw(), nw, nh)
    }

    fn decode_image_data(source: &gltf::image::Source, base_path: Option<&Path>, buffers: &[gltf::buffer::Data], max_size: u32) -> Option<TextureData> {
        match source {
            gltf::image::Source::View { view, .. } => {
                let start = view.offset();
                let end = start + view.length();
                let data = &buffers[view.buffer().index()][start..end];
                let decoded = image::load_from_memory(data).ok()?;
                let (rgba, width, height) = Self::downsample_image(decoded, max_size);
                Some(TextureData { rgba, width, height })
            }
            gltf::image::Source::Uri { uri, .. } => {
                let path = base_path.unwrap_or_else(|| Path::new(".")).join(uri);
                let decoded = image::open(&path).ok()?;
                let (rgba, width, height) = Self::downsample_image(decoded, max_size);
                Some(TextureData { rgba, width, height })
            }
        }
    }

    fn process_textures(
        doc: &gltf::Document,
        base_path: Option<&Path>,
        buffers: &[gltf::buffer::Data],
        max_size: u32,
    ) -> Vec<Option<TextureData>> {
        doc.textures()
            .map(|tex| Self::decode_image_data(&tex.source().source(), base_path, buffers, max_size))
            .collect()
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
        textures: &[Option<TextureData>],
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        bgl_mat: &wgpu::BindGroupLayout,
        default_view: &wgpu::TextureView,
        default_sampler: &wgpu::Sampler,
    ) -> Vec<Material> {
        let root = doc.as_json();
        let mut texture_views: HashMap<usize, wgpu::TextureView> = HashMap::new();
        let mut materials = Vec::new();

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

            let texture_view = pbr.base_color_texture().and_then(|info| {
                let tex_idx = info.texture().index();
                let td = textures.get(tex_idx)?.as_ref()?;
                let view = texture_views
                    .entry(tex_idx)
                    .or_insert_with(|| Self::create_texture_view(device, queue, td));
                Some(&*view)
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
        mat_offset: usize,
        materials_len: usize,
        device: &wgpu::Device,
    ) -> (Vec<Vec<GpuPrimitive>>, Vec<(Vec3, Vec3)>, Vec<Vec<RawPrimitiveData>>) {
        let built: Vec<_> = doc.meshes()
            .map(|mesh| {
                let mut mesh_min = Vec3::splat(f32::MAX);
                let mut mesh_max = Vec3::splat(f32::MIN);
                let mut raw_prims = Vec::new();

                let primitives: Vec<GpuPrimitive> = mesh.primitives()
                    .filter_map(|prim| {
                        let reader = prim.reader(|b| Some(&buffers[b.index()]));
                        let positions: Vec<[f32; 3]> = reader.read_positions()?.collect();
                        let mut prim_min = Vec3::splat(f32::MAX);
                        let mut prim_max = Vec3::splat(f32::MIN);
                        for p in &positions {
                            let v = Vec3::from_slice(p);
                            mesh_min = mesh_min.min(v);
                            mesh_max = mesh_max.max(v);
                            prim_min = prim_min.min(v);
                            prim_max = prim_max.max(v);
                        }
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

                        let color0: Vec<[f32; 4]> = reader
                            .read_colors(0)
                            .map(|c| c.into_rgba_f32().collect())
                            .unwrap_or_default();

                        let color1: Vec<[f32; 4]> = reader
                            .read_colors(1)
                            .map(|c| c.into_rgba_f32().collect())
                            .unwrap_or_default();

                        raw_prims.push(RawPrimitiveData {
                            positions: positions.iter().map(|p| Vec3::from_slice(p)).collect(),
                            normals: normals.iter().map(|n| Vec3::from_slice(n)).collect(),
                            indices: indices.clone().unwrap_or_else(|| (0..positions.len() as u32).collect()),
                            color0,
                            color1,
                        });

                        let local_mat_idx = prim.material().index().unwrap_or(0);
                        let final_mat_idx = (mat_offset + local_mat_idx).min(materials_len - 1);

                        Some(GpuPrimitive {
                            pos_buffer: Self::create_buffer(device, "Pos", bytemuck::cast_slice(&positions), wgpu::BufferUsages::VERTEX),
                            norm_buffer: Self::create_buffer(device, "Norm", bytemuck::cast_slice(&normals), wgpu::BufferUsages::VERTEX),
                            uv_buffer: Self::create_buffer(device, "UV", bytemuck::cast_slice(&uvs), wgpu::BufferUsages::VERTEX),
                            index_buffer: indices.as_ref().map(|idx| {
                                Self::create_buffer(device, "Idx", bytemuck::cast_slice(idx), wgpu::BufferUsages::INDEX)
                            }),
                            count,
                            material_index: final_mat_idx,
                            center,
                        })
                    })
                    .collect();

                let bounds = if mesh_min.x <= mesh_max.x {
                    (mesh_min, mesh_max)
                } else {
                    (Vec3::ZERO, Vec3::ZERO)
                };
                (primitives, bounds, raw_prims)
            })
            .collect();

        let mut primitives_by_mesh = Vec::with_capacity(built.len());
        let mut mesh_bounds = Vec::with_capacity(built.len());
        let mut raw_by_mesh = Vec::with_capacity(built.len());
        for (primitives, bounds, raw_prims) in built {
            primitives_by_mesh.push(primitives);
            mesh_bounds.push(bounds);
            raw_by_mesh.push(raw_prims);
        }
        (primitives_by_mesh, mesh_bounds, raw_by_mesh)
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
        mesh_bounds: &[(Vec3, Vec3)],
        raw_by_mesh: &[Vec<RawPrimitiveData>],
    ) -> (Vec<RenderNode>, HashMap<String, SurfaceData>, Vec<SceneCamera>, Vec<SceneLight>, (Vec3, Vec3)) {
        let mut render_nodes = Vec::new();
        let mut surfaces = HashMap::new();
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
            let node_name = node.name().map(String::from);

            if let Some(mesh) = node.mesh() {
                let mesh_index = mesh.index();
                if let Some(prims) = raw_by_mesh.get(mesh_index) {
                    let mut pos = Vec::new();
                    let mut norm = Vec::new();
                    let mut idx = Vec::new();
                    let mut c0 = Vec::new();
                    let mut c1 = Vec::new();
                    let mut base = 0u32;
                    for p in prims {
                        pos.extend_from_slice(&p.positions);
                        norm.extend_from_slice(&p.normals);
                        c0.extend_from_slice(&p.color0);
                        c1.extend_from_slice(&p.color1);
                        for &i in &p.indices {
                            idx.push(i + base);
                        }
                        base += p.positions.len() as u32;
                    }
                    if let Some(name) = &node_name {
                        surfaces.insert(name.clone(), SurfaceData {
                            name: name.clone(),
                            positions: pos,
                            normals: norm,
                            indices: idx,
                            color0: c0,
                            color1: c1,
                            world_transform,
                        });
                    }
                }

                let raw = InstanceRaw::from_transform(world_transform);
                let instance_buffer = Self::create_buffer(
                    device,
                    "NodeInstance",
                    bytemuck::bytes_of(&raw),
                    wgpu::BufferUsages::VERTEX,
                );
                render_nodes.push(RenderNode {
                    name: node_name.clone(),
                    world_transform,
                    instance_buffer,
                    instance_count: 1,
                    mesh_index,
                });

                if let Some(&(min, max)) = mesh_bounds.get(mesh_index) {
                    Self::expand_bounds(min, max, &world_transform, &mut bounds_min, &mut bounds_max);
                }
            }

            if let Some(cam) = node.camera() {
                let (yfov, znear, zfar) = match cam.projection() {
                    gltf::camera::Projection::Perspective(p) => (p.yfov(), p.znear(), p.zfar()),
                    gltf::camera::Projection::Orthographic(o) => (o.ymag(), o.znear(), Some(o.zfar())),
                };
                cameras.push(SceneCamera {
                    name: cam.name().map(String::from).or_else(|| node_name.clone()),
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
                    name: light.name().map(String::from).or_else(|| node_name.clone()),
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

        (render_nodes, surfaces, cameras, lights, bounds)
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

// #region Scatter
struct LcgRng(u64);
impl LcgRng {
    fn new(seed: u64) -> Self {
        Self(seed.max(1))
    }
    fn next_u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        self.0
    }
    fn next_f32(&mut self) -> f32 {
        (self.next_u64() >> 32) as f32 / 4294967296.0
    }
}

fn resolve_surface_weights(surface: &SurfaceData, channel: u32, component: &str) -> Vec<f32> {
    let comp_idx = match component.to_uppercase().as_str() {
        "R" | "0" => 0,
        "G" | "1" => 1,
        "B" | "2" => 2,
        "A" | "3" => 3,
        _ => 0,
    };
    if channel == 1 && !surface.color1.is_empty() {
        surface.color1.iter().map(|c| c[comp_idx]).collect()
    } else if !surface.color0.is_empty() {
        surface.color0.iter().map(|c| c[comp_idx]).collect()
    } else {
        vec![1.0; surface.positions.len()]
    }
}

fn scatter_instances_on_surface(
    surface: &SurfaceData,
    weights: &[f32],
    rule: &ScatterRule,
) -> Vec<ScatterInstanceItem> {
    let tri_count = surface.indices.len() / 3;
    if tri_count == 0 || surface.positions.is_empty() {
        return Vec::new();
    }

    let mut cdf: Vec<f32> = Vec::with_capacity(tri_count);
    let mut running_sum = 0.0f32;

    for i in 0..tri_count {
        let i0 = surface.indices[3 * i] as usize;
        let i1 = surface.indices[3 * i + 1] as usize;
        let i2 = surface.indices[3 * i + 2] as usize;

        let p0 = surface.world_transform.transform_point3(surface.positions[i0]);
        let p1 = surface.world_transform.transform_point3(surface.positions[i1]);
        let p2 = surface.world_transform.transform_point3(surface.positions[i2]);

        let cross = (p1 - p0).cross(p2 - p0);
        let area = 0.5 * cross.length();

        let w0 = weights.get(i0).copied().unwrap_or(1.0);
        let w1 = weights.get(i1).copied().unwrap_or(1.0);
        let w2 = weights.get(i2).copied().unwrap_or(1.0);
        let avg_w = (w0 + w1 + w2) / 3.0;

        let tri_w = area * avg_w;
        running_sum += tri_w;
        cdf.push(running_sum);
    }

    if running_sum <= 1e-6 {
        return Vec::new();
    }

    let mut rng = LcgRng::new(rule.seed);
    let mut instances = Vec::with_capacity(rule.count);
    let normal_transform = Mat4::from_mat3(Mat3::from_mat4(surface.world_transform).inverse().transpose());
    let scale_range = (rule.scale_max - rule.scale_min).max(0.0);

    for _ in 0..rule.count {
        let target = rng.next_f32() * running_sum;
        let tri_idx = match cdf.binary_search_by(|val| val.total_cmp(&target)) {
            Ok(idx) => idx.min(tri_count - 1),
            Err(idx) => idx.min(tri_count - 1),
        };

        let i0 = surface.indices[3 * tri_idx] as usize;
        let i1 = surface.indices[3 * tri_idx + 1] as usize;
        let i2 = surface.indices[3 * tri_idx + 2] as usize;

        let p0 = surface.world_transform.transform_point3(surface.positions[i0]);
        let p1 = surface.world_transform.transform_point3(surface.positions[i1]);
        let p2 = surface.world_transform.transform_point3(surface.positions[i2]);

        let n0 = normal_transform.transform_vector3(surface.normals[i0]);
        let n1 = normal_transform.transform_vector3(surface.normals[i1]);
        let n2 = normal_transform.transform_vector3(surface.normals[i2]);

        let r1 = rng.next_f32();
        let r2 = rng.next_f32();
        let sqrt_r1 = r1.sqrt();
        let u = 1.0 - sqrt_r1;
        let v = r2 * sqrt_r1;
        let w = 1.0 - u - v;

        let pos = p0 * u + p1 * v + p2 * w;
        let norm = (n0 * u + n1 * v + n2 * w).normalize();

        let up = if norm.y.abs() < 0.99 { Vec3::Y } else { Vec3::X };
        let tangent = up.cross(norm).normalize();
        let bitangent = norm.cross(tangent);

        let (rot_tangent, rot_bitangent) = if rule.yaw_random {
            let yaw = rng.next_f32() * std::f32::consts::TAU;
            let cos_y = yaw.cos();
            let sin_y = yaw.sin();
            (tangent * cos_y + bitangent * sin_y, -tangent * sin_y + bitangent * cos_y)
        } else {
            (tangent, bitangent)
        };

        let scale = rule.scale_min + rng.next_f32() * scale_range;
        let offset_pos = pos + norm * rule.normal_offset;

        let model = Mat4::from_cols(
            (rot_tangent * scale).extend(0.0),
            (norm * scale).extend(0.0),
            (rot_bitangent * scale).extend(0.0),
            offset_pos.extend(1.0),
        );

        let world_radius = rule.bounding_sphere_radius * scale;
        instances.push(ScatterInstanceItem {
            transform: InstanceRaw::from_transform(model),
            position: offset_pos,
            world_radius,
        });
    }

    instances
}

impl GltfScene {
    fn load_prototype_asset(
        path: &Path,
        materials: &mut Vec<Material>,
        primitives_by_mesh: &mut Vec<Vec<GpuPrimitive>>,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        bgl_mat: &wgpu::BindGroupLayout,
        default_view: &wgpu::TextureView,
        default_sampler: &wgpu::Sampler,
        max_texture_size: u32,
    ) -> Result<usize, Box<dyn std::error::Error>> {
        let base = path.parent().unwrap_or_else(|| Path::new("."));
        let gltf = gltf::Gltf::from_reader_without_validation(std::io::BufReader::new(std::fs::File::open(path)?))?;
        let buffers = gltf::import_buffers(&gltf.document, Some(base), gltf.blob)?;
        let textures = Self::process_textures(&gltf.document, Some(base), &buffers, max_texture_size);
        let mat_offset = materials.len();
        let mut new_materials = Self::build_materials(&gltf.document, &textures, device, queue, bgl_mat, default_view, default_sampler);
        materials.append(&mut new_materials);

        let (mut new_prims, _, _) = Self::build_primitives(&gltf.document, &buffers, mat_offset, materials.len(), device);
        let proto_mesh_idx = primitives_by_mesh.len();
        primitives_by_mesh.append(&mut new_prims);
        Ok(proto_mesh_idx)
    }

    #[allow(clippy::too_many_arguments)]
    fn apply_scatter_rules(
        scatter_config_path: Option<&str>,
        base_dir: &Path,
        surfaces: &HashMap<String, SurfaceData>,
        materials: &mut Vec<Material>,
        primitives_by_mesh: &mut Vec<Vec<GpuPrimitive>>,
        render_nodes: &mut Vec<RenderNode>,
        scatter_groups: &mut Vec<ScatterLodGroup>,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        bgl_mat: &wgpu::BindGroupLayout,
        default_view: &wgpu::TextureView,
        default_sampler: &wgpu::Sampler,
        max_texture_size: u32,
    ) {
        let config_path = match scatter_config_path {
            Some(p) => PathBuf::from(p),
            None => return,
        };
        if !config_path.exists() {
            crate::telemetry::log_info("GltfLoader", "Scatter", &format!("Scatter config '{}' not found, skipping procedural scattering.", config_path.display()));
            return;
        }
        let data = match std::fs::read_to_string(&config_path) {
            Ok(d) => d,
            Err(e) => {
                crate::telemetry::log_warn("GltfLoader", "Scatter", &format!("Failed to read scatter config: {e}"));
                return;
            }
        };
        let rules: Vec<ScatterRule> = match serde_json::from_str(&data) {
            Ok(r) => r,
            Err(e) => {
                crate::telemetry::log_warn("GltfLoader", "Scatter", &format!("Failed to parse scatter config: {e}"));
                return;
            }
        };

        for rule in rules {
            if !rule.enabled {
                continue;
            }
            let surface = match surfaces.get(&rule.target_surface_node) {
                Some(s) => s,
                None => {
                    crate::telemetry::log_warn("GltfLoader", "Scatter", &format!("Target surface '{}' not found in scene for rule '{}'", rule.target_surface_node, rule.name));
                    continue;
                }
            };

            let weights = resolve_surface_weights(surface, rule.weight_channel, &rule.weight_component);
            let instances = scatter_instances_on_surface(surface, &weights, &rule);
            let total_count = instances.len();
            if total_count == 0 {
                continue;
            }

            if !rule.lods.is_empty() {
                let mut lod_levels = Vec::new();
                for lod_cfg in &rule.lods {
                    let proto_path = if Path::new(&lod_cfg.prototype_asset).is_absolute() {
                        PathBuf::from(&lod_cfg.prototype_asset)
                    } else {
                        base_dir.join(&lod_cfg.prototype_asset)
                    };
                    if !proto_path.exists() {
                        crate::telemetry::log_warn("GltfLoader", "Scatter", &format!("LOD prototype asset '{}' not found for rule '{}'", proto_path.display(), rule.name));
                        continue;
                    }

                    match Self::load_prototype_asset(&proto_path, materials, primitives_by_mesh, device, queue, bgl_mat, default_view, default_sampler, max_texture_size) {
                        Ok(proto_mesh_idx) => {
                            let max_byte_size = (total_count * std::mem::size_of::<InstanceRaw>()) as u64;
                            let instance_buffer = device.create_buffer(&wgpu::BufferDescriptor {
                                label: Some(&format!("{}_LOD{}_Instances", rule.name, lod_cfg.lod_level)),
                                size: max_byte_size.max(64),
                                usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
                                mapped_at_creation: false,
                            });
                            let node_idx = render_nodes.len();
                            render_nodes.push(RenderNode {
                                name: Some(format!("{}_LOD{}", rule.name, lod_cfg.lod_level)),
                                world_transform: Mat4::IDENTITY,
                                instance_buffer,
                                instance_count: 0,
                                mesh_index: proto_mesh_idx,
                            });
                            lod_levels.push(ScatterLodLevel {
                                mesh_index: proto_mesh_idx,
                                render_node_index: node_idx,
                                min_screen_coverage_percent: lod_cfg.min_screen_coverage_percent,
                            });
                        }
                        Err(e) => {
                            crate::telemetry::log_warn("GltfLoader", "Scatter", &format!("Failed to load LOD prototype '{}': {e}", proto_path.display()));
                        }
                    }
                }

                lod_levels.sort_by(|a, b| b.min_screen_coverage_percent.total_cmp(&a.min_screen_coverage_percent));
                crate::telemetry::log_info(
                    "GltfLoader",
                    "Scatter",
                    &format!(
                        "Configured rule '{}': generated {} candidate instances across {} LOD levels onto '{}'",
                        rule.name, total_count, lod_levels.len(), rule.target_surface_node
                    ),
                );

                scatter_groups.push(ScatterLodGroup {
                    name: rule.name.clone(),
                    instances,
                    lods: lod_levels,
                    cull_screen_coverage_percent: rule.cull_screen_coverage_percent,
                    last_eval_cam: None,
                });
            } else if let Some(ref proto) = rule.prototype_asset {
                let proto_path = if Path::new(proto).is_absolute() {
                    PathBuf::from(proto)
                } else {
                    base_dir.join(proto)
                };
                if !proto_path.exists() {
                    crate::telemetry::log_warn("GltfLoader", "Scatter", &format!("Prototype asset '{}' not found for rule '{}'", proto_path.display(), rule.name));
                    continue;
                }

                match Self::load_prototype_asset(&proto_path, materials, primitives_by_mesh, device, queue, bgl_mat, default_view, default_sampler, max_texture_size) {
                    Ok(proto_mesh_idx) => {
                        let raw_transforms: Vec<InstanceRaw> = instances.iter().map(|it| it.transform).collect();
                        let instance_buffer = Self::create_buffer(
                            device,
                            &format!("{}_Instances", rule.name),
                            bytemuck::cast_slice(&raw_transforms),
                            wgpu::BufferUsages::VERTEX,
                        );
                        crate::telemetry::log_info(
                            "GltfLoader",
                            "Scatter",
                            &format!(
                                "Applied rule '{}': generated {} GPU instances of '{}' onto '{}'",
                                rule.name, raw_transforms.len(), proto, rule.target_surface_node
                            ),
                        );
                        render_nodes.push(RenderNode {
                            name: Some(rule.name),
                            world_transform: Mat4::IDENTITY,
                            instance_buffer,
                            instance_count: raw_transforms.len() as u32,
                            mesh_index: proto_mesh_idx,
                        });
                    }
                    Err(e) => {
                        crate::telemetry::log_warn("GltfLoader", "Scatter", &format!("Failed to load prototype '{}': {e}", proto_path.display()));
                    }
                }
            } else {
                crate::telemetry::log_warn("GltfLoader", "Scatter", &format!("Rule '{}' has neither 'lods' nor 'prototype_asset' specified.", rule.name));
            }
        }
    }

    pub fn update_lods(&mut self, queue: &wgpu::Queue, cam_pos: Vec3, aspect: f32, yfov: f32) {
        if self.scatter_groups.is_empty() {
            return;
        }

        let tan_half_fov = (yfov * 0.5).tan();
        let denom_factor = 4.0 * aspect * tan_half_fov * tan_half_fov;
        if denom_factor <= 1e-6 {
            return;
        }

        for group in &mut self.scatter_groups {
            if let Some((last_pos, last_asp, last_fov)) = group.last_eval_cam {
                if last_pos.distance_squared(cam_pos) < 1e-4
                    && (last_asp - aspect).abs() < 1e-4
                    && (last_fov - yfov).abs() < 1e-4
                {
                    continue;
                }
            }
            group.last_eval_cam = Some((cam_pos, aspect, yfov));

            let lod_count = group.lods.len();
            let mut buckets: Vec<Vec<InstanceRaw>> = vec![Vec::new(); lod_count];
            let mut culled_count = 0usize;

            for inst in &group.instances {
                let dist = inst.position.distance(cam_pos);
                if dist <= 1e-4 {
                    if let Some(b) = buckets.first_mut() {
                        b.push(inst.transform);
                    }
                    continue;
                }

                let r = inst.world_radius;
                let coverage_pct = (std::f32::consts::PI * r * r) / (denom_factor * dist * dist) * 100.0;

                if coverage_pct < group.cull_screen_coverage_percent {
                    culled_count += 1;
                    continue;
                }

                let mut assigned = false;
                for (lod_idx, lod) in group.lods.iter().enumerate() {
                    if coverage_pct >= lod.min_screen_coverage_percent {
                        buckets[lod_idx].push(inst.transform);
                        assigned = true;
                        break;
                    }
                }
                if !assigned {
                    if let Some(b) = buckets.last_mut() {
                        b.push(inst.transform);
                    } else {
                        culled_count += 1;
                    }
                }
            }

            let mut log_stats = Vec::new();
            for (lod_idx, lod) in group.lods.iter().enumerate() {
                let bucket = &buckets[lod_idx];
                let node = &mut self.render_nodes[lod.render_node_index];
                node.instance_count = bucket.len() as u32;
                if !bucket.is_empty() {
                    queue.write_buffer(&node.instance_buffer, 0, bytemuck::cast_slice(bucket));
                }
                log_stats.push(format!("LOD{}: {}", lod_idx, bucket.len()));
            }

            crate::telemetry::log_info(
                "GltfLoader",
                "LOD",
                &format!(
                    "Screen coverage distribution for '{}': {} | Culled: {}",
                    group.name,
                    log_stats.join(", "),
                    culled_count
                ),
            );
        }
    }
}
// #endregion

// #region Core
impl GltfScene {
    #[allow(clippy::too_many_arguments)]
    pub fn load<P: AsRef<Path>>(
        path: P, scatter_cfg: Option<&str>, device: &wgpu::Device, queue: &wgpu::Queue,
        bgl_mat: &wgpu::BindGroupLayout, view: &wgpu::TextureView, sampler: &wgpu::Sampler, max_tex: u32,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        let (path, base) = (path.as_ref(), path.as_ref().parent().unwrap_or_else(|| Path::new(".")));
        let gltf = gltf::Gltf::from_reader_without_validation(std::io::BufReader::new(std::fs::File::open(path)?))?;
        let buffers = gltf::import_buffers(&gltf.document, Some(base), gltf.blob)?;
        let textures = Self::process_textures(&gltf.document, Some(base), &buffers, max_tex);
        crate::telemetry::log_info("GltfLoader", "Load", &format!("Reading glTF scene: {}", path.display()));
        let mut materials = Self::build_materials(&gltf.document, &textures, device, queue, bgl_mat, view, sampler);
        drop(textures);
        let (mut primitives_by_mesh, bounds, raw) = Self::build_primitives(&gltf.document, &buffers, 0, materials.len(), device);
        let (mut render_nodes, surfaces, cameras, lights, aabb) = Self::build_render_nodes(&gltf.document, device, &bounds, &raw);
        let (camera, light) = (Self::enforce_single_camera_policy(cameras, &aabb), Self::resolve_active_light(lights));
        let mut scatter_groups = Vec::new();
        Self::apply_scatter_rules(scatter_cfg, base, &surfaces, &mut materials, &mut primitives_by_mesh, &mut render_nodes, &mut scatter_groups, device, queue, bgl_mat, view, sampler, max_tex);
        crate::telemetry::log_info("GltfLoader", "Init", &format!("Loaded {} meshes, {} materials, {} instances.", primitives_by_mesh.len(), materials.len(), render_nodes.len()));
        Ok(Self { primitives_by_mesh, materials, render_nodes, camera, light, scatter_groups })
    }
}
// #endregion
