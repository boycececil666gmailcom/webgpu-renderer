// #region Imports
use wgpu::util::DeviceExt;
// #endregion

// #region Types
#[repr(C)]
#[derive(Copy, Clone, Debug, bytemuck::Pod, bytemuck::Zeroable)]
pub struct MaterialUniforms {
    pub base_color: [f32; 4],
    pub metallic: f32,
    pub roughness: f32,
    pub clearcoat: f32,
    pub alpha_cutoff: f32,
    pub use_texture: u32,
    pub is_unlit: u32,
    pub alpha_mode: u32,
    pub _padding: u32,
}

pub struct Material {
    pub uniform_buffer: wgpu::Buffer,
    pub bind_group: wgpu::BindGroup,
    pub is_transparent: bool,
    pub double_sided: bool,
    pub has_texture: bool,
}
// #endregion

// #region Scaffolding
impl Material {
    fn create_uniform_buffer(device: &wgpu::Device, uniforms: &MaterialUniforms) -> wgpu::Buffer {
        device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("Material Uniform Buffer"),
            contents: bytemuck::bytes_of(uniforms),
            usage: wgpu::BufferUsages::UNIFORM,
        })
    }

    fn create_bind_group(
        device: &wgpu::Device,
        layout: &wgpu::BindGroupLayout,
        uniform_buffer: &wgpu::Buffer,
        view: &wgpu::TextureView,
        sampler: &wgpu::Sampler,
    ) -> wgpu::BindGroup {
        device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("Material BindGroup"),
            layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: uniform_buffer.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::TextureView(view),
                },
                wgpu::BindGroupEntry {
                    binding: 2,
                    resource: wgpu::BindingResource::Sampler(sampler),
                },
            ],
        })
    }
}
// #endregion

// #region Core
impl Material {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        device: &wgpu::Device, layout: &wgpu::BindGroupLayout, default_view: &wgpu::TextureView,
        default_sampler: &wgpu::Sampler, texture_view: Option<&wgpu::TextureView>, base_color: [f32; 4],
        metallic: f32, roughness: f32, clearcoat: f32, alpha_cutoff: f32,
        alpha_mode: u32, is_unlit: bool, is_transparent: bool, double_sided: bool,
    ) -> Self {
        let has_texture = texture_view.is_some();
        let view = texture_view.unwrap_or(default_view);
        let uniforms = MaterialUniforms {
            base_color,
            metallic,
            roughness,
            clearcoat,
            alpha_cutoff,
            use_texture: if has_texture { 1 } else { 0 },
            is_unlit: if is_unlit { 1 } else { 0 },
            alpha_mode,
            _padding: 0,
        };
        let uniform_buffer = Self::create_uniform_buffer(device, &uniforms);
        let bind_group = Self::create_bind_group(device, layout, &uniform_buffer, view, default_sampler);

        Self { uniform_buffer, bind_group, is_transparent, double_sided, has_texture }
    }
}
// #endregion
