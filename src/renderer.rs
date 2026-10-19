// #region Imports
use std::borrow::Cow;
use std::sync::Arc;

use glam::{Mat4, Vec3};

use crate::gltf_loader::{GltfScene, GpuPrimitive, RenderNode, SceneLight};
use crate::material::Material;
// #endregion

// #region Types
const LIGHT_INTENSITY_NORMALIZATION: f32 = 1000.0;

#[repr(C)]
#[derive(Copy, Clone, Debug, bytemuck::Pod, bytemuck::Zeroable)]
pub struct FrameUniforms {
    pub view: [[f32; 4]; 4],
    pub projection: [[f32; 4]; 4],
    pub cam_pos: [f32; 4],
    pub light_dir: [f32; 4],
    pub light_color: [f32; 4],
}

pub struct Renderer {
    pub device: Arc<wgpu::Device>,
    pub queue: Arc<wgpu::Queue>,
    pub bgl_frame: wgpu::BindGroupLayout,
    pub bgl_obj: Arc<wgpu::BindGroupLayout>,
    pub bgl_mat: Arc<wgpu::BindGroupLayout>,
    pub default_view: Arc<wgpu::TextureView>,
    pub default_sampler: Arc<wgpu::Sampler>,
    pub env_view: Arc<wgpu::TextureView>,
    pub env_sampler: Arc<wgpu::Sampler>,
    pub frame_buffer: wgpu::Buffer,
    pub frame_bind_group: wgpu::BindGroup,
    pub pipeline_opaque: wgpu::RenderPipeline,
    pub pipeline_opaque_double_sided: wgpu::RenderPipeline,
    pub pipeline_transparent: wgpu::RenderPipeline,
    pub pipeline_transparent_double_sided: wgpu::RenderPipeline,
    pub depth_texture: wgpu::Texture,
    pub depth_view: wgpu::TextureView,
    pub depth_size: (u32, u32),
    pub clear_color: wgpu::Color,
    transparent_draws: Vec<(f32, usize, usize)>,
}
// #endregion

// #region Scaffolding
impl Renderer {
    fn create_default_texture(
        device: &wgpu::Device,
        queue: &wgpu::Queue,
    ) -> (wgpu::TextureView, wgpu::Sampler) {
        let default_texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Default 1x1 White Texture"),
            size: wgpu::Extent3d {
                width: 1,
                height: 1,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8UnormSrgb,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });

        queue.write_texture(
            wgpu::ImageCopyTexture {
                texture: &default_texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            &[255, 255, 255, 255],
            wgpu::ImageDataLayout {
                offset: 0,
                bytes_per_row: Some(4),
                rows_per_image: Some(1),
            },
            wgpu::Extent3d {
                width: 1,
                height: 1,
                depth_or_array_layers: 1,
            },
        );

        let default_view = default_texture.create_view(&wgpu::TextureViewDescriptor::default());
        let default_sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("Default Sampler"),
            address_mode_u: wgpu::AddressMode::Repeat,
            address_mode_v: wgpu::AddressMode::Repeat,
            address_mode_w: wgpu::AddressMode::Repeat,
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            mipmap_filter: wgpu::FilterMode::Linear,
            ..Default::default()
        });

        (default_view, default_sampler)
    }

    fn create_bind_group_layouts(
        device: &wgpu::Device,
    ) -> (wgpu::BindGroupLayout, wgpu::BindGroupLayout, wgpu::BindGroupLayout) {
        let bgl_frame = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("Frame BindGroupLayout"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::VERTEX | wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Texture {
                        sample_type: wgpu::TextureSampleType::Float { filterable: true },
                        view_dimension: wgpu::TextureViewDimension::D2,
                        multisampled: false,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 2,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                    count: None,
                },
            ],
        });

        let bgl_obj = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("Object BindGroupLayout"),
            entries: &[wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::VERTEX,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: None,
                },
                count: None,
            }],
        });

        let bgl_mat = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("Material BindGroupLayout"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Texture {
                        sample_type: wgpu::TextureSampleType::Float { filterable: true },
                        view_dimension: wgpu::TextureViewDimension::D2,
                        multisampled: false,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 2,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                    count: None,
                },
            ],
        });

        (bgl_frame, bgl_obj, bgl_mat)
    }

    fn load_environment_texture(
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        path: &str,
    ) -> (wgpu::TextureView, wgpu::Sampler) {
        let loaded = std::fs::read(path).ok().and_then(|bytes| {
            image::load_from_memory(&bytes).ok().map(|img| img.to_rgba8())
        });

        let (width, height, rgba) = match loaded {
            Some(img) => {
                let (w, h) = img.dimensions();
                crate::telemetry::log_info("Renderer", "IBL", &format!("Loaded environment map '{path}' ({w}x{h})"));
                (w, h, img.into_raw())
            }
            None => {
                crate::telemetry::log_warn("Renderer", "IBL", &format!("Could not load environment map at '{path}', using neutral sky fallback"));
                (2, 2, vec![
                    180, 200, 230, 255,  180, 200, 230, 255,
                    120, 110, 100, 255,  120, 110, 100, 255,
                ])
            }
        };

        let mip_level_count = 32 - width.max(height).leading_zeros();
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Environment Map Texture"),
            size: wgpu::Extent3d {
                width,
                height,
                depth_or_array_layers: 1,
            },
            mip_level_count,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8UnormSrgb,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });

        let mut level = image::RgbaImage::from_raw(width, height, rgba)
            .expect("valid RGBA texture buffer");

        for mip_level in 0..mip_level_count {
            let (w, h) = level.dimensions();
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
                    bytes_per_row: Some(4 * w),
                    rows_per_image: Some(h),
                },
                wgpu::Extent3d {
                    width: w,
                    height: h,
                    depth_or_array_layers: 1,
                },
            );

            if mip_level + 1 < mip_level_count {
                level = image::imageops::resize(
                    &level,
                    (w / 2).max(1),
                    (h / 2).max(1),
                    image::imageops::FilterType::Triangle,
                );
            }
        }

        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("Environment Sampler"),
            address_mode_u: wgpu::AddressMode::Repeat,
            address_mode_v: wgpu::AddressMode::ClampToEdge,
            address_mode_w: wgpu::AddressMode::ClampToEdge,
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            mipmap_filter: wgpu::FilterMode::Linear,
            ..Default::default()
        });

        (view, sampler)
    }

    fn create_frame_uniforms(
        device: &wgpu::Device,
        bgl_frame: &wgpu::BindGroupLayout,
        env_view: &wgpu::TextureView,
        env_sampler: &wgpu::Sampler,
    ) -> (wgpu::Buffer, wgpu::BindGroup) {
        let frame_buffer = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("Frame Uniform Buffer"),
            size: std::mem::size_of::<FrameUniforms>() as u64,
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });

        let frame_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("Frame BindGroup"),
            layout: bgl_frame,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: frame_buffer.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::TextureView(env_view),
                },
                wgpu::BindGroupEntry {
                    binding: 2,
                    resource: wgpu::BindingResource::Sampler(env_sampler),
                },
            ],
        });

        (frame_buffer, frame_bind_group)
    }

    fn create_pipelines(
        device: &wgpu::Device,
        surface_format: wgpu::TextureFormat,
        bgl_frame: &wgpu::BindGroupLayout,
        bgl_obj: &wgpu::BindGroupLayout,
        bgl_mat: &wgpu::BindGroupLayout,
        shader_src: &str,
    ) -> (wgpu::RenderPipeline, wgpu::RenderPipeline, wgpu::RenderPipeline, wgpu::RenderPipeline) {
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("Render Pipeline Layout"),
            bind_group_layouts: &[bgl_frame, bgl_obj, bgl_mat],
            push_constant_ranges: &[],
        });

        let vertex_buffers = [
            wgpu::VertexBufferLayout {
                array_stride: 12,
                step_mode: wgpu::VertexStepMode::Vertex,
                attributes: &[wgpu::VertexAttribute {
                    format: wgpu::VertexFormat::Float32x3,
                    offset: 0,
                    shader_location: 0,
                }],
            },
            wgpu::VertexBufferLayout {
                array_stride: 12,
                step_mode: wgpu::VertexStepMode::Vertex,
                attributes: &[wgpu::VertexAttribute {
                    format: wgpu::VertexFormat::Float32x3,
                    offset: 0,
                    shader_location: 1,
                }],
            },
            wgpu::VertexBufferLayout {
                array_stride: 8,
                step_mode: wgpu::VertexStepMode::Vertex,
                attributes: &[wgpu::VertexAttribute {
                    format: wgpu::VertexFormat::Float32x2,
                    offset: 0,
                    shader_location: 2,
                }],
            },
        ];

        let module = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("Standard PBR Shader Module"),
            source: wgpu::ShaderSource::Wgsl(Cow::Borrowed(shader_src)),
        });

        let make_pipeline = |label: &str, depth_write: bool, cull: Option<wgpu::Face>| {
            device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                label: Some(label),
                layout: Some(&pipeline_layout),
                vertex: wgpu::VertexState {
                    module: &module,
                    entry_point: Some("vs_main"),
                    buffers: &vertex_buffers,
                    compilation_options: Default::default(),
                },
                fragment: Some(wgpu::FragmentState {
                    module: &module,
                    entry_point: Some("fs_main"),
                    targets: &[Some(wgpu::ColorTargetState {
                        format: surface_format,
                        blend: if depth_write {
                            None
                        } else {
                            Some(wgpu::BlendState::ALPHA_BLENDING)
                        },
                        write_mask: wgpu::ColorWrites::ALL,
                    })],
                    compilation_options: Default::default(),
                }),
                primitive: wgpu::PrimitiveState {
                    topology: wgpu::PrimitiveTopology::TriangleList,
                    cull_mode: cull,
                    ..Default::default()
                },
                depth_stencil: Some(wgpu::DepthStencilState {
                    format: wgpu::TextureFormat::Depth24Plus,
                    depth_write_enabled: depth_write,
                    depth_compare: wgpu::CompareFunction::Less,
                    stencil: wgpu::StencilState::default(),
                    bias: wgpu::DepthBiasState::default(),
                }),
                multisample: wgpu::MultisampleState::default(),
                multiview: None,
                cache: None,
            })
        };

        let pipeline_opaque = make_pipeline("Opaque PBR Pipeline", true, Some(wgpu::Face::Back));
        let pipeline_opaque_double_sided = make_pipeline("Opaque PBR Double Sided Pipeline", true, None);
        let pipeline_transparent = make_pipeline("Transparent PBR Pipeline", false, Some(wgpu::Face::Back));
        let pipeline_transparent_double_sided = make_pipeline("Transparent PBR Double Sided Pipeline", false, None);

        (
            pipeline_opaque,
            pipeline_opaque_double_sided,
            pipeline_transparent,
            pipeline_transparent_double_sided,
        )
    }

    fn create_depth_texture(
        device: &wgpu::Device,
        width: u32,
        height: u32,
    ) -> (wgpu::Texture, wgpu::TextureView) {
        let w = width.max(1);
        let h = height.max(1);
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Depth Texture"),
            size: wgpu::Extent3d {
                width: w,
                height: h,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Depth24Plus,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            view_formats: &[],
        });
        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        (texture, view)
    }

    pub fn resize(&mut self, width: u32, height: u32) {
        if self.depth_size != (width, height) {
            let (tex, view) = Self::create_depth_texture(&self.device, width, height);
            self.depth_texture = tex;
            self.depth_view = view;
            self.depth_size = (width, height);
        }
    }

    fn update_frame_uniforms(&self, view: Mat4, projection: Mat4, light: &SceneLight, cam_pos: Vec3) {
        let frame_uniforms = FrameUniforms {
            view: view.to_cols_array_2d(),
            projection: projection.to_cols_array_2d(),
            cam_pos: [cam_pos.x, cam_pos.y, cam_pos.z, 1.0],
            light_dir: [light.direction.x, light.direction.y, light.direction.z, 0.0],
            light_color: [
                light.color[0],
                light.color[1],
                light.color[2],
                light.intensity / LIGHT_INTENSITY_NORMALIZATION,
            ],
        };
        self.queue.write_buffer(
            &self.frame_buffer,
            0,
            bytemuck::bytes_of(&frame_uniforms),
        );
    }

    fn build_transparent_draws(&mut self, view: Mat4, scene: &GltfScene) {
        self.transparent_draws.clear();
        for (node_index, node) in scene.render_nodes.iter().enumerate() {
            let Some(primitives) = scene.primitives_by_mesh.get(node.mesh_index) else {
                continue;
            };
            for (prim_index, prim) in primitives.iter().enumerate() {
                if !scene.materials[prim.material_index].is_transparent {
                    continue;
                }
                let world_center = node.world_transform.transform_point3(prim.center);
                let depth = view.transform_point3(world_center).z;
                self.transparent_draws.push((depth, node_index, prim_index));
            }
        }
        self.transparent_draws.sort_by(|a, b| a.0.total_cmp(&b.0));
    }

    fn pipeline_for(&self, material: &Material) -> &wgpu::RenderPipeline {
        match (material.is_transparent, material.double_sided) {
            (false, false) => &self.pipeline_opaque,
            (false, true) => &self.pipeline_opaque_double_sided,
            (true, false) => &self.pipeline_transparent,
            (true, true) => &self.pipeline_transparent_double_sided,
        }
    }

    fn record_render_pass(
        &mut self,
        encoder: &mut wgpu::CommandEncoder,
        output_view: &wgpu::TextureView,
        view: Mat4,
        scene: &GltfScene,
    ) {
        self.build_transparent_draws(view, scene);

        let mut render_pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
            label: Some("Main Render Pass"),
            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                view: output_view,
                resolve_target: None,
                ops: wgpu::Operations {
                    load: wgpu::LoadOp::Clear(self.clear_color),
                    store: wgpu::StoreOp::Store,
                },
            })],
            depth_stencil_attachment: Some(wgpu::RenderPassDepthStencilAttachment {
                view: &self.depth_view,
                depth_ops: Some(wgpu::Operations {
                    load: wgpu::LoadOp::Clear(1.0),
                    store: wgpu::StoreOp::Store,
                }),
                stencil_ops: None,
            }),
            timestamp_writes: None,
            occlusion_query_set: None,
        });

        render_pass.set_bind_group(0, &self.frame_bind_group, &[]);

        for node in &scene.render_nodes {
            let Some(primitives) = scene.primitives_by_mesh.get(node.mesh_index) else {
                continue;
            };
            for prim in primitives {
                let material = &scene.materials[prim.material_index];
                if material.is_transparent {
                    continue;
                }
                draw_primitive(&mut render_pass, self.pipeline_for(material), node, prim, material);
            }
        }

        for &(_, node_index, prim_index) in &self.transparent_draws {
            let node = &scene.render_nodes[node_index];
            let Some(primitives) = scene.primitives_by_mesh.get(node.mesh_index) else {
                continue;
            };
            let Some(prim) = primitives.get(prim_index) else {
                continue;
            };
            let material = &scene.materials[prim.material_index];
            draw_primitive(&mut render_pass, self.pipeline_for(material), node, prim, material);
        }
    }
}

fn draw_primitive(
    render_pass: &mut wgpu::RenderPass,
    pipeline: &wgpu::RenderPipeline,
    node: &RenderNode,
    prim: &GpuPrimitive,
    material: &Material,
) {
    render_pass.set_pipeline(pipeline);
    render_pass.set_bind_group(1, &node.bind_group, &[]);
    render_pass.set_bind_group(2, &material.bind_group, &[]);
    render_pass.set_vertex_buffer(0, prim.pos_buffer.slice(..));
    render_pass.set_vertex_buffer(1, prim.norm_buffer.slice(..));
    render_pass.set_vertex_buffer(2, prim.uv_buffer.slice(..));

    if let Some(index_buf) = &prim.index_buffer {
        render_pass.set_index_buffer(index_buf.slice(..), wgpu::IndexFormat::Uint32);
        render_pass.draw_indexed(0..prim.count, 0, 0..1);
    } else {
        render_pass.draw(0..prim.count, 0..1);
    }
}
// #endregion

// #region Core
impl Renderer {
    pub fn new(
        device: wgpu::Device,
        queue: wgpu::Queue,
        surface_format: wgpu::TextureFormat,
        width: u32,
        height: u32,
        shader_source: &str,
        env_map_path: &str,
    ) -> Self {
        let device = Arc::new(device);
        let queue = Arc::new(queue);
        let (default_view, default_sampler) = Self::create_default_texture(&device, &queue);
        let (env_view, env_sampler) = Self::load_environment_texture(&device, &queue, env_map_path);
        let (bgl_frame, bgl_obj, bgl_mat) = Self::create_bind_group_layouts(&device);
        let (frame_buffer, frame_bind_group) = Self::create_frame_uniforms(&device, &bgl_frame, &env_view, &env_sampler);
        let (
            pipeline_opaque,
            pipeline_opaque_double_sided,
            pipeline_transparent,
            pipeline_transparent_double_sided,
        ) = Self::create_pipelines(&device, surface_format, &bgl_frame, &bgl_obj, &bgl_mat, shader_source);
        let (depth_texture, depth_view) = Self::create_depth_texture(&device, width, height);

        crate::telemetry::log_info("Renderer", "Init", "Unified PBR pipelines initialized successfully.");

        Self {
            device,
            queue,
            bgl_frame,
            bgl_obj: Arc::new(bgl_obj),
            bgl_mat: Arc::new(bgl_mat),
            default_view: Arc::new(default_view),
            default_sampler: Arc::new(default_sampler),
            env_view: Arc::new(env_view),
            env_sampler: Arc::new(env_sampler),
            frame_buffer,
            frame_bind_group,
            pipeline_opaque,
            pipeline_opaque_double_sided,
            pipeline_transparent,
            pipeline_transparent_double_sided,
            depth_texture,
            depth_view,
            depth_size: (width, height),
            clear_color: wgpu::Color {
                r: 0.42,
                g: 0.65,
                b: 0.85,
                a: 1.0,
            },
            transparent_draws: Vec::new(),
        }
    }

    pub fn render_clear(&self, output: &wgpu::TextureView) {
        let mut encoder = self.device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
            label: Some("Clear Command Encoder"),
        });
        encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
            label: Some("Clear Render Pass"),
            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                view: output,
                resolve_target: None,
                ops: wgpu::Operations {
                    load: wgpu::LoadOp::Clear(self.clear_color),
                    store: wgpu::StoreOp::Store,
                },
            })],
            depth_stencil_attachment: None,
            timestamp_writes: None,
            occlusion_query_set: None,
        });
        self.queue.submit(std::iter::once(encoder.finish()));
    }

    pub fn render_frame(
        &mut self,
        output: &wgpu::TextureView,
        view: Mat4,
        proj: Mat4,
        light: &SceneLight,
        cam_pos: Vec3,
        scene: &GltfScene,
    ) {
        self.update_frame_uniforms(view, proj, light, cam_pos);
        let mut enc = self.device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
            label: Some("Frame Command Encoder"),
        });
        self.record_render_pass(&mut enc, output, view, scene);
        self.queue.submit(std::iter::once(enc.finish()));
    }
}
// #endregion
