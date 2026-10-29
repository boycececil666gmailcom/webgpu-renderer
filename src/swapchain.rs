// #region Imports
use std::sync::Arc;
use winit::window::Window;

use crate::preprocessing::telemetry::{log_error, log_info};
// #endregion

// #region Types
pub struct Swapchain {
    pub surface: wgpu::Surface<'static>,
    pub config: wgpu::SurfaceConfiguration,
}
// #endregion

// #region Core
impl Swapchain {
    pub fn create_surface(
        instance: &wgpu::Instance,
        window: Arc<Window>,
    ) -> Result<wgpu::Surface<'static>, wgpu::CreateSurfaceError> {
        instance.create_surface(window)
    }

    pub fn from_surface(
        surface: wgpu::Surface<'static>,
        adapter: &wgpu::Adapter,
        device: &wgpu::Device,
        width: u32,
        height: u32,
    ) -> Self {
        let surface_caps = surface.get_capabilities(adapter);
        let surface_format = surface_caps
            .formats
            .iter()
            .copied()
            .find(|f| f.is_srgb())
            .unwrap_or(surface_caps.formats[0]);

        let width = width.max(1);
        let height = height.max(1);

        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format: surface_format,
            width,
            height,
            present_mode: wgpu::PresentMode::AutoVsync,
            alpha_mode: surface_caps.alpha_modes[0],
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
        };
        surface.configure(device, &config);

        Self { surface, config }
    }

    pub fn new(
        window: Arc<Window>,
        instance: &wgpu::Instance,
        adapter: &wgpu::Adapter,
        device: &wgpu::Device,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        let surface = match Self::create_surface(instance, window.clone()) {
            Ok(s) => s,
            Err(e) => {
                log_error("Presentation", "Fatal", &format!("Failed to create WebGPU surface: {e:?}"));
                return Err(Box::new(e));
            }
        };

        let size = window.inner_size();
        Ok(Self::from_surface(surface, adapter, device, size.width, size.height))
    }

    pub fn format(&self) -> wgpu::TextureFormat {
        self.config.format
    }

    pub fn resize(&mut self, device: &wgpu::Device, width: u32, height: u32) {
        if width > 0 && height > 0 {
            self.config.width = width;
            self.config.height = height;
            self.surface.configure(device, &self.config);
            log_info("Presentation", "Lifecycle", &format!("Surface resized: {width}x{height}"));
        }
    }

    pub fn reconfigure(&self, device: &wgpu::Device) {
        self.surface.configure(device, &self.config);
    }

    pub fn aspect_ratio(&self) -> f32 {
        self.config.width as f32 / self.config.height.max(1) as f32
    }

    pub fn acquire_frame(&self) -> Result<wgpu::SurfaceTexture, wgpu::SurfaceError> {
        self.surface.get_current_texture()
    }

    pub fn present_frame(&self, frame: wgpu::SurfaceTexture) {
        frame.present();
    }
}
// #endregion

// #region Tests
#[cfg(test)]
mod tests {
    #[test]
    fn test_swapchain_aspect_ratio_calculation() {
        let width = 1920u32;
        let height = 1080u32;
        let ratio = width as f32 / height.max(1) as f32;
        assert!((ratio - (16.0 / 9.0)).abs() < 1e-4);

        let zero_h = 0u32;
        let ratio_zero = 800u32 as f32 / zero_h.max(1) as f32;
        assert_eq!(ratio_zero, 800.0);
    }
}
// #endregion
