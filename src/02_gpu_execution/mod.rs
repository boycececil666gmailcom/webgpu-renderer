// #region Imports
pub mod renderer;

pub use renderer::{DrawItem, FrameUniforms, Renderer};
// #endregion

// #region Tests
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_frame_uniforms_layout() {
        let uniforms = FrameUniforms {
            view: [[0.0; 4]; 4],
            projection: [[0.0; 4]; 4],
            cam_pos: [0.0; 4],
        };
        let bytes = bytemuck::bytes_of(&uniforms);
        // 16 floats (view) + 16 floats (proj) + 4 (cam_pos) = 36 floats = 144 bytes
        assert_eq!(bytes.len(), 144);
    }

    #[test]
    fn test_draw_order_sorting() {
        let mut opaque = vec![
            DrawItem { distance_sq: 100.0, node_index: 0, prim_index: 0 },
            DrawItem { distance_sq: 4.0, node_index: 1, prim_index: 0 },
            DrawItem { distance_sq: 25.0, node_index: 2, prim_index: 0 },
        ];
        // Front-to-Back: ascending distance
        opaque.sort_by(|a, b| a.distance_sq.total_cmp(&b.distance_sq));
        assert_eq!(opaque[0].distance_sq, 4.0);
        assert_eq!(opaque[1].distance_sq, 25.0);
        assert_eq!(opaque[2].distance_sq, 100.0);

        let mut transparent = vec![
            DrawItem { distance_sq: 4.0, node_index: 1, prim_index: 0 },
            DrawItem { distance_sq: 100.0, node_index: 0, prim_index: 0 },
            DrawItem { distance_sq: 25.0, node_index: 2, prim_index: 0 },
        ];
        // Back-to-Front: descending distance
        transparent.sort_by(|a, b| b.distance_sq.total_cmp(&a.distance_sq));
        assert_eq!(transparent[0].distance_sq, 100.0);
        assert_eq!(transparent[1].distance_sq, 25.0);
        assert_eq!(transparent[2].distance_sq, 4.0);
    }

    #[test]
    fn test_wgpu_bc_texture_upload() {
        let instance = wgpu::Instance::default();
        let adapter = match pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default())) {
            Some(a) => a,
            None => return,
        };
        if !adapter.features().contains(wgpu::Features::TEXTURE_COMPRESSION_BC) {
            return;
        }

        let (device, queue) = match pollster::block_on(adapter.request_device(
            &wgpu::DeviceDescriptor {
                label: Some("BC Test Device"),
                required_features: wgpu::Features::TEXTURE_COMPRESSION_BC,
                required_limits: wgpu::Limits::default(),
                memory_hints: Default::default(),
            },
            None,
        )) {
            Ok(pair) => pair,
            Err(_) => return,
        };

        let (w, h) = (16u32, 16u32);
        let mip_count = 5u32; // 16x16, 8x8, 4x4, 2x2, 1x1
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("BC1 Test Texture"),
            size: wgpu::Extent3d { width: w, height: h, depth_or_array_layers: 1 },
            mip_level_count: mip_count,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Bc1RgbaUnormSrgb,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });

        let block_bytes = 8u32;
        for mip in 0..mip_count {
            let mw = (w >> mip).max(1);
            let mh = (h >> mip).max(1);
            let blocks_x = (mw + 3) / 4;
            let blocks_y = (mh + 3) / 4;
            let compressed_bytes = (blocks_x * blocks_y * block_bytes) as usize;
            let dummy_data = vec![0xAAu8; compressed_bytes];

            queue.write_texture(
                wgpu::ImageCopyTexture {
                    texture: &texture,
                    mip_level: mip,
                    origin: wgpu::Origin3d::ZERO,
                    aspect: wgpu::TextureAspect::All,
                },
                &dummy_data,
                wgpu::ImageDataLayout {
                    offset: 0,
                    bytes_per_row: Some(blocks_x * block_bytes),
                    rows_per_image: Some(blocks_y),
                },
                wgpu::Extent3d { width: blocks_x * 4, height: blocks_y * 4, depth_or_array_layers: 1 },
            );
        }
    }
}
// #endregion
