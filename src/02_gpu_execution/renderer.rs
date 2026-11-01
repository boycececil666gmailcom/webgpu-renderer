// #region Imports
use std::borrow::Cow;
use std::sync::Arc;

use glam::{Mat4, Vec3};

use crate::preprocessing::gltf_loader::{GltfScene, GpuPrimitive, RenderNode};
use crate::preprocessing::material::Material;
use crate::preprocessing::telemetry::log_info;
// #endregion

// #region Types
#[repr(C)]
#[derive(Copy, Clone, Debug, bytemuck::Pod, bytemuck::Zeroable)]
pub struct FrameUniforms {
    pub view: [[f32; 4]; 4],
    pub projection: [[f32; 4]; 4],
    pub cam_pos: [f32; 4],
    pub sun_view_proj: [[f32; 4]; 4],
    pub sun_dir: [f32; 4],
    pub sun_color: [f32; 4],
}

#[derive(Copy, Clone, Debug)]
pub struct DrawItem {
    pub distance_sq: f32,
    pub node_index: usize,
    pub prim_index: usize,
}

pub struct Renderer {
    pub device: Arc<wgpu::Device>,
    pub queue: Arc<wgpu::Queue>,
    pub bgl_frame: wgpu::BindGroupLayout,
    pub bgl_mat: Arc<wgpu::BindGroupLayout>,
    pub default_view: Arc<wgpu::TextureView>,
    pub default_sampler: Arc<wgpu::Sampler>,
    pub env_view: Arc<wgpu::TextureView>,
    pub env_sampler: Arc<wgpu::Sampler>,
    pub shadow_texture: wgpu::Texture,
    pub shadow_view: Arc<wgpu::TextureView>,
    pub shadow_sampler: Arc<wgpu::Sampler>,
    pub shadow_frame_bind_group: wgpu::BindGroup,
    pub frame_buffer: wgpu::Buffer,
    pub frame_bind_group: wgpu::BindGroup,
    pub pipeline_opaque: wgpu::RenderPipeline,
    pub pipeline_opaque_double_sided: wgpu::RenderPipeline,
    pub pipeline_masked: wgpu::RenderPipeline,
    pub pipeline_masked_double_sided: wgpu::RenderPipeline,
    pub pipeline_transparent: wgpu::RenderPipeline,
    pub pipeline_transparent_double_sided: wgpu::RenderPipeline,
    pub pipeline_shadow_opaque: wgpu::RenderPipeline,
    pub pipeline_shadow_opaque_double_sided: wgpu::RenderPipeline,
    pub pipeline_shadow_masked: wgpu::RenderPipeline,
    pub depth_texture: wgpu::Texture,
    pub depth_view: wgpu::TextureView,
    pub depth_size: (u32, u32),
    pub clear_color: wgpu::Color,
    opaque_draws: Vec<DrawItem>,
    masked_draws: Vec<DrawItem>,
    transparent_draws: Vec<DrawItem>,
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
            anisotropy_clamp: 16,
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
                wgpu::BindGroupLayoutEntry {
                    binding: 3,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Texture {
                        sample_type: wgpu::TextureSampleType::Depth,
                        view_dimension: wgpu::TextureViewDimension::D2,
                        multisampled: false,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 4,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Comparison),
                    count: None,
                },
            ],
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

        let bgl_shadow_frame = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("Shadow Frame BindGroupLayout"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::VERTEX,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
            ],
        });

        (bgl_frame, bgl_mat, bgl_shadow_frame)
    }

    fn load_environment_texture(
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        path: &str,
        env_intensity: f32,
    ) -> (wgpu::TextureView, wgpu::Sampler) {
        let loaded = std::fs::read(path).ok().and_then(|bytes| {
            image::load_from_memory(&bytes).ok()
        });

        let (width, height, rgba) = match loaded {
            Some(image::DynamicImage::ImageRgb32F(img)) => {
                let (w, h) = img.dimensions();
                let effective_scale = if env_intensity > 0.0 { env_intensity } else { 10.0 };
                crate::telemetry::log_info("Renderer", "IBL", &format!("Loaded HDR environment map '{path}' ({w}x{h}) with Reinhard tone mapping and sRGB encoding (scale {effective_scale}x)"));
                let mut out = Vec::with_capacity((w * h * 4) as usize);
                for pixel in img.pixels() {
                    let r = pixel[0] * effective_scale;
                    let g = pixel[1] * effective_scale;
                    let b = pixel[2] * effective_scale;
                    let r_tm = r / (1.0 + r);
                    let g_tm = g / (1.0 + g);
                    let b_tm = b / (1.0 + b);
                    let to_srgb = |c: f32| -> u8 {
                        let s = if c <= 0.0031308 {
                            c * 12.92
                        } else {
                            1.055 * c.powf(1.0 / 2.4) - 0.055
                        };
                        (s * 255.0).clamp(0.0, 255.0).round() as u8
                    };
                    out.push(to_srgb(r_tm));
                    out.push(to_srgb(g_tm));
                    out.push(to_srgb(b_tm));
                    out.push(255);
                }
                (w, h, out)
            }
            Some(image::DynamicImage::ImageRgba32F(img)) => {
                let (w, h) = img.dimensions();
                let effective_scale = if env_intensity > 0.0 { env_intensity } else { 10.0 };
                crate::telemetry::log_info("Renderer", "IBL", &format!("Loaded HDR environment map '{path}' ({w}x{h}) with Reinhard tone mapping and sRGB encoding (scale {effective_scale}x)"));
                let mut out = Vec::with_capacity((w * h * 4) as usize);
                for pixel in img.pixels() {
                    let r = pixel[0] * effective_scale;
                    let g = pixel[1] * effective_scale;
                    let b = pixel[2] * effective_scale;
                    let r_tm = r / (1.0 + r);
                    let g_tm = g / (1.0 + g);
                    let b_tm = b / (1.0 + b);
                    let to_srgb = |c: f32| -> u8 {
                        let s = if c <= 0.0031308 {
                            c * 12.92
                        } else {
                            1.055 * c.powf(1.0 / 2.4) - 0.055
                        };
                        (s * 255.0).clamp(0.0, 255.0).round() as u8
                    };
                    out.push(to_srgb(r_tm));
                    out.push(to_srgb(g_tm));
                    out.push(to_srgb(b_tm));
                    out.push(255);
                }
                (w, h, out)
            }
            Some(ldr_img) => {
                let img = ldr_img.to_rgba8();
                let (w, h) = img.dimensions();
                crate::telemetry::log_info("Renderer", "IBL", &format!("Loaded LDR environment map '{path}' ({w}x{h})"));
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

    fn create_shadow_texture(
        device: &wgpu::Device,
        size: u32,
    ) -> (wgpu::Texture, wgpu::TextureView, wgpu::Sampler) {
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Shadow Depth Texture"),
            size: wgpu::Extent3d {
                width: size,
                height: size,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Depth32Float,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::TEXTURE_BINDING,
            view_formats: &[],
        });
        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("Shadow Comparison Sampler"),
            address_mode_u: wgpu::AddressMode::ClampToEdge,
            address_mode_v: wgpu::AddressMode::ClampToEdge,
            address_mode_w: wgpu::AddressMode::ClampToEdge,
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            compare: Some(wgpu::CompareFunction::LessEqual),
            ..Default::default()
        });
        (texture, view, sampler)
    }

    fn create_frame_uniforms(
        device: &wgpu::Device,
        bgl_frame: &wgpu::BindGroupLayout,
        bgl_shadow_frame: &wgpu::BindGroupLayout,
        env_view: &wgpu::TextureView,
        env_sampler: &wgpu::Sampler,
        shadow_view: &wgpu::TextureView,
        shadow_sampler: &wgpu::Sampler,
    ) -> (wgpu::Buffer, wgpu::BindGroup, wgpu::BindGroup) {
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
                wgpu::BindGroupEntry {
                    binding: 3,
                    resource: wgpu::BindingResource::TextureView(shadow_view),
                },
                wgpu::BindGroupEntry {
                    binding: 4,
                    resource: wgpu::BindingResource::Sampler(shadow_sampler),
                },
            ],
        });

        let shadow_frame_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("Shadow Frame BindGroup"),
            layout: bgl_shadow_frame,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: frame_buffer.as_entire_binding(),
                },
            ],
        });

        (frame_buffer, frame_bind_group, shadow_frame_bind_group)
    }

    fn create_pipelines(
        device: &wgpu::Device,
        surface_format: wgpu::TextureFormat,
        bgl_frame: &wgpu::BindGroupLayout,
        bgl_shadow_frame: &wgpu::BindGroupLayout,
        bgl_mat: &wgpu::BindGroupLayout,
        shader_src: &str,
    ) -> (
        wgpu::RenderPipeline,
        wgpu::RenderPipeline,
        wgpu::RenderPipeline,
        wgpu::RenderPipeline,
        wgpu::RenderPipeline,
        wgpu::RenderPipeline,
        wgpu::RenderPipeline,
        wgpu::RenderPipeline,
        wgpu::RenderPipeline,
    ) {
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("Render Pipeline Layout"),
            bind_group_layouts: &[bgl_frame, bgl_mat],
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
            wgpu::VertexBufferLayout {
                array_stride: 128,
                step_mode: wgpu::VertexStepMode::Instance,
                attributes: &[
                    wgpu::VertexAttribute {
                        format: wgpu::VertexFormat::Float32x4,
                        offset: 0,
                        shader_location: 3,
                    },
                    wgpu::VertexAttribute {
                        format: wgpu::VertexFormat::Float32x4,
                        offset: 16,
                        shader_location: 4,
                    },
                    wgpu::VertexAttribute {
                        format: wgpu::VertexFormat::Float32x4,
                        offset: 32,
                        shader_location: 5,
                    },
                    wgpu::VertexAttribute {
                        format: wgpu::VertexFormat::Float32x4,
                        offset: 48,
                        shader_location: 6,
                    },
                    wgpu::VertexAttribute {
                        format: wgpu::VertexFormat::Float32x4,
                        offset: 64,
                        shader_location: 7,
                    },
                    wgpu::VertexAttribute {
                        format: wgpu::VertexFormat::Float32x4,
                        offset: 80,
                        shader_location: 8,
                    },
                    wgpu::VertexAttribute {
                        format: wgpu::VertexFormat::Float32x4,
                        offset: 96,
                        shader_location: 9,
                    },
                    wgpu::VertexAttribute {
                        format: wgpu::VertexFormat::Float32x4,
                        offset: 112,
                        shader_location: 10,
                    },
                ],
            },
        ];

        let module = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("Standard PBR Shader Module"),
            source: wgpu::ShaderSource::Wgsl(Cow::Borrowed(shader_src)),
        });

        let make_pipeline = |label: &str, entry_point: &str, depth_write: bool, cull: Option<wgpu::Face>| {
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
                    entry_point: Some(entry_point),
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

        // 1. Solid opaque (fs_opaque has ZERO discard statements; full hardware Early-Z raster writes)
        let pipeline_opaque = make_pipeline("Opaque PBR Pipeline", "fs_opaque", true, Some(wgpu::Face::Back));
        let pipeline_opaque_double_sided = make_pipeline("Opaque PBR Double Sided Pipeline", "fs_opaque", true, None);
        // 2. Alpha-tested foliage cutout (fs_masked discards based on alpha cutoff)
        let pipeline_masked = make_pipeline("Masked PBR Pipeline", "fs_masked", true, Some(wgpu::Face::Back));
        let pipeline_masked_double_sided = make_pipeline("Masked PBR Double Sided Pipeline", "fs_masked", true, None);
        // 3. Alpha-blended transparent (fs_transparent without depth writes)
        let pipeline_transparent = make_pipeline("Transparent PBR Pipeline", "fs_transparent", false, Some(wgpu::Face::Back));
        let pipeline_transparent_double_sided = make_pipeline("Transparent PBR Double Sided Pipeline", "fs_transparent", false, None);

        // 4. Shadow pipelines (depth-only pass from sun's perspective with isolated uniform layout)
        let shadow_pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("Shadow Pipeline Layout"),
            bind_group_layouts: &[bgl_shadow_frame, bgl_mat],
            push_constant_ranges: &[],
        });

        let make_shadow_pipeline = |label: &str, cull: Option<wgpu::Face>| {
            device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                label: Some(label),
                layout: Some(&shadow_pipeline_layout),
                vertex: wgpu::VertexState {
                    module: &module,
                    entry_point: Some("vs_shadow"),
                    buffers: &vertex_buffers,
                    compilation_options: Default::default(),
                },
                fragment: None,
                primitive: wgpu::PrimitiveState {
                    topology: wgpu::PrimitiveTopology::TriangleList,
                    cull_mode: cull,
                    ..Default::default()
                },
                depth_stencil: Some(wgpu::DepthStencilState {
                    format: wgpu::TextureFormat::Depth32Float,
                    depth_write_enabled: true,
                    depth_compare: wgpu::CompareFunction::LessEqual,
                    stencil: wgpu::StencilState::default(),
                    bias: wgpu::DepthBiasState {
                        constant: 2,
                        slope_scale: 2.0,
                        clamp: 0.0,
                    },
                }),
                multisample: wgpu::MultisampleState::default(),
                multiview: None,
                cache: None,
            })
        };

        let pipeline_shadow_opaque = make_shadow_pipeline("Shadow Opaque Pipeline", Some(wgpu::Face::Back));
        let pipeline_shadow_opaque_double_sided = make_shadow_pipeline("Shadow Opaque Double Sided Pipeline", None);

        let pipeline_shadow_masked = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("Shadow Masked Pipeline"),
            layout: Some(&shadow_pipeline_layout),
            vertex: wgpu::VertexState {
                module: &module,
                entry_point: Some("vs_shadow_masked"),
                buffers: &vertex_buffers,
                compilation_options: Default::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &module,
                entry_point: Some("fs_shadow_masked"),
                targets: &[],
                compilation_options: Default::default(),
            }),
            primitive: wgpu::PrimitiveState {
                topology: wgpu::PrimitiveTopology::TriangleList,
                cull_mode: None,
                ..Default::default()
            },
            depth_stencil: Some(wgpu::DepthStencilState {
                format: wgpu::TextureFormat::Depth32Float,
                depth_write_enabled: true,
                depth_compare: wgpu::CompareFunction::LessEqual,
                stencil: wgpu::StencilState::default(),
                bias: wgpu::DepthBiasState {
                    constant: 2,
                    slope_scale: 2.0,
                    clamp: 0.0,
                },
            }),
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });

        (
            pipeline_opaque,
            pipeline_opaque_double_sided,
            pipeline_masked,
            pipeline_masked_double_sided,
            pipeline_transparent,
            pipeline_transparent_double_sided,
            pipeline_shadow_opaque,
            pipeline_shadow_opaque_double_sided,
            pipeline_shadow_masked,
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

    fn update_frame_uniforms(&self, view: Mat4, projection: Mat4, cam_pos: Vec3) {
        let sun_dir = Vec3::new(-0.25, 0.88, 0.38).normalize();
        let sun_color = [6.0, 5.7, 5.2, 1.0];

        let view_inv = view.inverse();
        let cam_forward = view_inv.transform_vector3(-Vec3::Z).normalize();
        let ray_dist = if cam_pos.y.abs() > 0.1 && cam_forward.y.abs() > 0.05 {
            (cam_pos.y.abs() / cam_forward.y.abs()).clamp(4.0, 35.0)
        } else {
            12.0
        };
        let ground_focus = Vec3::new(
            cam_pos.x + cam_forward.x * ray_dist,
            0.0,
            cam_pos.z + cam_forward.z * ray_dist,
        );

        let sun_pos = ground_focus + sun_dir * 70.0;
        let light_view = Mat4::look_at_rh(sun_pos, ground_focus, Vec3::Y);
        let ortho_extent = 32.0;
        let light_proj = Mat4::orthographic_rh(
            -ortho_extent, ortho_extent,
            -ortho_extent, ortho_extent,
            1.0, 150.0,
        );
        let sun_view_proj = light_proj * light_view;

        let frame_uniforms = FrameUniforms {
            view: view.to_cols_array_2d(),
            projection: projection.to_cols_array_2d(),
            cam_pos: [cam_pos.x, cam_pos.y, cam_pos.z, 1.0],
            sun_view_proj: sun_view_proj.to_cols_array_2d(),
            sun_dir: [sun_dir.x, sun_dir.y, sun_dir.z, 0.0],
            sun_color,
        };
        self.queue.write_buffer(
            &self.frame_buffer,
            0,
            bytemuck::bytes_of(&frame_uniforms),
        );
    }

    fn build_draw_lists(&mut self, cam_pos: Vec3, scene: &GltfScene) {
        self.opaque_draws.clear();
        self.masked_draws.clear();
        self.transparent_draws.clear();

        for (node_index, node) in scene.render_nodes.iter().enumerate() {
            if node.instance_count == 0 {
                continue;
            }
            let Some(primitives) = scene.primitives_by_mesh.get(node.mesh_index) else {
                continue;
            };

            for (prim_index, prim) in primitives.iter().enumerate() {
                let material = &scene.materials[prim.material_index];
                let dist_sq = if node.instance_count > 1 {
                    node.min_cam_distance_sq
                } else {
                    let world_center = node.world_transform.transform_point3(prim.center);
                    cam_pos.distance_squared(world_center)
                };

                let item = DrawItem {
                    distance_sq: dist_sq,
                    node_index,
                    prim_index,
                };

                if material.is_transparent || material.alpha_mode == 2 {
                    self.transparent_draws.push(item);
                } else if material.is_masked() {
                    self.masked_draws.push(item);
                } else {
                    self.opaque_draws.push(item);
                }
            }
        }

        // 1. Solid Opaque: Front-to-Back (closest first to establish Early-Z occluder buffer)
        self.opaque_draws.sort_by(|a, b| a.distance_sq.total_cmp(&b.distance_sq));

        // 2. Alpha-tested foliage / cutout: Front-to-Back (closer leaves prime depth, farther leaves culled by Early-Z)
        self.masked_draws.sort_by(|a, b| a.distance_sq.total_cmp(&b.distance_sq));

        // 3. Transparent: Back-to-Front (farthest first for correct alpha blending accumulation)
        self.transparent_draws.sort_by(|a, b| b.distance_sq.total_cmp(&a.distance_sq));
    }

    fn pipeline_for(&self, material: &Material) -> &wgpu::RenderPipeline {
        if material.is_transparent || material.alpha_mode == 2 {
            if material.double_sided {
                &self.pipeline_transparent_double_sided
            } else {
                &self.pipeline_transparent
            }
        } else if material.is_masked() {
            if material.double_sided {
                &self.pipeline_masked_double_sided
            } else {
                &self.pipeline_masked
            }
        } else {
            if material.double_sided {
                &self.pipeline_opaque_double_sided
            } else {
                &self.pipeline_opaque
            }
        }
    }

    fn record_shadow_pass(&self, encoder: &mut wgpu::CommandEncoder, scene: &GltfScene) {
        let mut shadow_pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
            label: Some("Shadow Render Pass"),
            color_attachments: &[],
            depth_stencil_attachment: Some(wgpu::RenderPassDepthStencilAttachment {
                view: &self.shadow_view,
                depth_ops: Some(wgpu::Operations {
                    load: wgpu::LoadOp::Clear(1.0),
                    store: wgpu::StoreOp::Store,
                }),
                stencil_ops: None,
            }),
            timestamp_writes: None,
            occlusion_query_set: None,
        });

        shadow_pass.set_bind_group(0, &self.shadow_frame_bind_group, &[]);

        for &item in &self.opaque_draws {
            let node = &scene.render_nodes[item.node_index];
            if node.instance_count == 0 {
                continue;
            }
            let Some(primitives) = scene.primitives_by_mesh.get(node.mesh_index) else {
                continue;
            };
            let Some(prim) = primitives.get(item.prim_index) else {
                continue;
            };
            let material = &scene.materials[prim.material_index];
            if material.is_unlit {
                continue;
            }
            let pipeline = if material.double_sided {
                &self.pipeline_shadow_opaque_double_sided
            } else {
                &self.pipeline_shadow_opaque
            };
            draw_primitive(&mut shadow_pass, pipeline, node, prim, material);
        }

        for &item in &self.masked_draws {
            let node = &scene.render_nodes[item.node_index];
            if node.instance_count == 0 {
                continue;
            }
            let Some(primitives) = scene.primitives_by_mesh.get(node.mesh_index) else {
                continue;
            };
            let Some(prim) = primitives.get(item.prim_index) else {
                continue;
            };
            let material = &scene.materials[prim.material_index];
            if material.is_unlit {
                continue;
            }
            draw_primitive(&mut shadow_pass, &self.pipeline_shadow_masked, node, prim, material);
        }
    }

    fn record_render_pass(
        &mut self,
        encoder: &mut wgpu::CommandEncoder,
        output_view: &wgpu::TextureView,
        cam_pos: Vec3,
        scene: &GltfScene,
    ) -> crate::preprocessing::telemetry::FrameStats {
        self.build_draw_lists(cam_pos, scene);

        // Pre-pass: Render sun shadow depth map
        self.record_shadow_pass(encoder, scene);

        let mut draw_calls = 0u32;
        let mut triangles_drawn = 0u64;
        let mut instances_drawn = 0u32;
        let mut visited_nodes = vec![false; scene.render_nodes.len()];

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

        // Phase 1: Solid Opaque (Front-to-Back) - primes Z-buffer with unconditional depth writes
        for &item in &self.opaque_draws {
            let node = &scene.render_nodes[item.node_index];
            if node.instance_count == 0 {
                continue;
            }
            let Some(primitives) = scene.primitives_by_mesh.get(node.mesh_index) else {
                continue;
            };
            let Some(prim) = primitives.get(item.prim_index) else {
                continue;
            };
            let material = &scene.materials[prim.material_index];
            if !visited_nodes[item.node_index] {
                visited_nodes[item.node_index] = true;
                instances_drawn += node.instance_count;
            }
            draw_primitive(&mut render_pass, self.pipeline_for(material), node, prim, material);
            draw_calls += 1;
            triangles_drawn += (prim.count as u64 / 3) * (node.instance_count as u64);
        }

        // Phase 2: Masked Foliage / Cutout (Front-to-Back) - Early-Z rejection against solid occluders
        for &item in &self.masked_draws {
            let node = &scene.render_nodes[item.node_index];
            if node.instance_count == 0 {
                continue;
            }
            let Some(primitives) = scene.primitives_by_mesh.get(node.mesh_index) else {
                continue;
            };
            let Some(prim) = primitives.get(item.prim_index) else {
                continue;
            };
            let material = &scene.materials[prim.material_index];
            if !visited_nodes[item.node_index] {
                visited_nodes[item.node_index] = true;
                instances_drawn += node.instance_count;
            }
            draw_primitive(&mut render_pass, self.pipeline_for(material), node, prim, material);
            draw_calls += 1;
            triangles_drawn += (prim.count as u64 / 3) * (node.instance_count as u64);
        }

        // Phase 3: Transparent (Back-to-Front) - Alpha blending with depth read
        for &item in &self.transparent_draws {
            let node = &scene.render_nodes[item.node_index];
            if node.instance_count == 0 {
                continue;
            }
            let Some(primitives) = scene.primitives_by_mesh.get(node.mesh_index) else {
                continue;
            };
            let Some(prim) = primitives.get(item.prim_index) else {
                continue;
            };
            let material = &scene.materials[prim.material_index];
            if !visited_nodes[item.node_index] {
                visited_nodes[item.node_index] = true;
                instances_drawn += node.instance_count;
            }
            draw_primitive(&mut render_pass, self.pipeline_for(material), node, prim, material);
            draw_calls += 1;
            triangles_drawn += (prim.count as u64 / 3) * (node.instance_count as u64);
        }

        crate::preprocessing::telemetry::FrameStats {
            draw_calls,
            triangles_drawn,
            instances_drawn,
        }
    }

    pub fn render_target_vram_bytes(&self) -> u64 {
        let (w, h) = self.depth_size;
        // Color buffer (RGBA8: 4 bytes) + Depth buffer (Depth24Plus: 4 bytes) + Shadow buffer (2048x2048 Depth32: 16 MB)
        (w as u64) * (h as u64) * 8 + (2048 * 2048 * 4)
    }
}

fn draw_primitive(
    render_pass: &mut wgpu::RenderPass,
    pipeline: &wgpu::RenderPipeline,
    node: &RenderNode,
    prim: &GpuPrimitive,
    material: &Material,
) {
    if node.instance_count == 0 {
        return;
    }
    render_pass.set_pipeline(pipeline);
    render_pass.set_bind_group(1, &material.bind_group, &[]);
    render_pass.set_vertex_buffer(0, prim.pos_buffer.slice(..));
    render_pass.set_vertex_buffer(1, prim.norm_buffer.slice(..));
    render_pass.set_vertex_buffer(2, prim.uv_buffer.slice(..));
    render_pass.set_vertex_buffer(3, node.instance_buffer.slice(..));

    if let Some(index_buf) = &prim.index_buffer {
        render_pass.set_index_buffer(index_buf.slice(..), wgpu::IndexFormat::Uint32);
        render_pass.draw_indexed(0..prim.count, 0, 0..node.instance_count);
    } else {
        render_pass.draw(0..prim.count, 0..node.instance_count);
    }
}
// #endregion

// #region Engine
impl Renderer {
    pub fn new(
        device: wgpu::Device,
        queue: wgpu::Queue,
        surface_format: wgpu::TextureFormat,
        width: u32,
        height: u32,
        shader_source: &str,
        env_map_path: &str,
        env_intensity: f32,
    ) -> Self {
        let device = Arc::new(device);
        let queue = Arc::new(queue);
        let (default_view, default_sampler) = Self::create_default_texture(&device, &queue);
        let (env_view, env_sampler) = Self::load_environment_texture(&device, &queue, env_map_path, env_intensity);
        let (shadow_texture, shadow_view, shadow_sampler) = Self::create_shadow_texture(&device, 2048);
        let (bgl_frame, bgl_mat, bgl_shadow_frame) = Self::create_bind_group_layouts(&device);
        let (frame_buffer, frame_bind_group, shadow_frame_bind_group) = Self::create_frame_uniforms(
            &device,
            &bgl_frame,
            &bgl_shadow_frame,
            &env_view,
            &env_sampler,
            &shadow_view,
            &shadow_sampler,
        );
        let (
            pipeline_opaque,
            pipeline_opaque_double_sided,
            pipeline_masked,
            pipeline_masked_double_sided,
            pipeline_transparent,
            pipeline_transparent_double_sided,
            pipeline_shadow_opaque,
            pipeline_shadow_opaque_double_sided,
            pipeline_shadow_masked,
        ) = Self::create_pipelines(&device, surface_format, &bgl_frame, &bgl_shadow_frame, &bgl_mat, shader_source);
        let (depth_texture, depth_view) = Self::create_depth_texture(&device, width, height);

        log_info("Renderer", "Init", "Unified PBR pipelines initialized successfully.");

        Self {
            device,
            queue,
            bgl_frame,
            bgl_mat: Arc::new(bgl_mat),
            default_view: Arc::new(default_view),
            default_sampler: Arc::new(default_sampler),
            env_view: Arc::new(env_view),
            env_sampler: Arc::new(env_sampler),
            shadow_texture,
            shadow_view: Arc::new(shadow_view),
            shadow_sampler: Arc::new(shadow_sampler),
            shadow_frame_bind_group,
            frame_buffer,
            frame_bind_group,
            pipeline_opaque,
            pipeline_opaque_double_sided,
            pipeline_masked,
            pipeline_masked_double_sided,
            pipeline_transparent,
            pipeline_transparent_double_sided,
            pipeline_shadow_opaque,
            pipeline_shadow_opaque_double_sided,
            pipeline_shadow_masked,
            depth_texture,
            depth_view,
            depth_size: (width, height),
            clear_color: wgpu::Color {
                r: 0.42,
                g: 0.65,
                b: 0.85,
                a: 1.0,
            },
            opaque_draws: Vec::new(),
            masked_draws: Vec::new(),
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
}
// #endregion

// #region Core
impl Renderer {
    pub fn render_frame(
        &mut self,
        output: &wgpu::TextureView,
        view: Mat4,
        proj: Mat4,
        cam_pos: Vec3,
        scene: &GltfScene,
    ) -> crate::preprocessing::telemetry::FrameStats {
        self.update_frame_uniforms(view, proj, cam_pos);
        let mut enc = self.device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
            label: Some("Frame Command Encoder"),
        });
        let stats = self.record_render_pass(&mut enc, output, cam_pos, scene);
        let submission = self.queue.submit(std::iter::once(enc.finish()));
        // The Android emulator Vulkan path can present frames with missing draws
        // while submissions overlap. Complete this frame before presenting it.
        self.device.poll(wgpu::Maintain::WaitForSubmissionIndex(submission));
        stats
    }
}
// #endregion
