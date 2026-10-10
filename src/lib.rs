// #region PublicApi
pub mod camera;
pub mod config;
pub mod gltf_loader;
pub mod material;
pub mod renderer;
pub mod transform;

pub use camera::Camera;
pub use config::Config;
pub use gltf_loader::GltfScene;
pub use material::Material;
pub use renderer::Renderer;

use std::sync::Arc;
use std::time::{Duration, Instant};

use winit::{
    dpi::PhysicalSize,
    event::{ElementState, Event, KeyEvent, WindowEvent},
    event_loop::EventLoop,
    keyboard::{KeyCode, PhysicalKey},
    window::WindowBuilder,
};

struct RenderState {
    surface: wgpu::Surface<'static>,
    surface_config: wgpu::SurfaceConfiguration,
    renderer: Renderer,
    scene: GltfScene,
    camera: Camera,
}

pub fn run_engine(event_loop: EventLoop<()>, model_path: &str) -> Result<(), Box<dyn std::error::Error>> {
    let config = Config::load();
    let window = Arc::new(
        WindowBuilder::new()
            .with_title("Antigravity WebGPU Engine (Rust)")
            .with_inner_size(PhysicalSize::new(config.scr_width, config.scr_height))
            .build(&event_loop)?,
    );

    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
        backends: wgpu::Backends::PRIMARY,
        ..Default::default()
    });

    let target_frame_time = if config.target_fps > 0 {
        Duration::from_secs_f64(1.0 / config.target_fps as f64)
    } else {
        Duration::ZERO
    };

    let model_path = model_path.to_string();
    let mut render_state: Option<RenderState> = None;

    event_loop.run(move |event, target| match event {
        Event::Resumed => {
            if render_state.is_none() {
                println!("[Engine-Lifecycle] Resumed event received. Initializing WebGPU surface...");
                let surface = match instance.create_surface(window.clone()) {
                    Ok(s) => s,
                    Err(e) => {
                        eprintln!("[Engine-Fatal] Failed to create WebGPU surface: {e:?}");
                        return;
                    }
                };

                let adapter = match pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
                    power_preference: wgpu::PowerPreference::HighPerformance,
                    compatible_surface: Some(&surface),
                    force_fallback_adapter: false,
                })) {
                    Some(a) => a,
                    None => {
                        eprintln!("[Engine-Fatal] Failed to find suitable GPU adapter");
                        return;
                    }
                };

                let (device, queue) = match pollster::block_on(adapter.request_device(
                    &wgpu::DeviceDescriptor {
                        label: Some("WebGPU Device"),
                        required_features: wgpu::Features::empty(),
                        required_limits: wgpu::Limits::default(),
                        memory_hints: Default::default(),
                    },
                    None,
                )) {
                    Ok(pair) => pair,
                    Err(e) => {
                        eprintln!("[Engine-Fatal] Failed to request device: {e:?}");
                        return;
                    }
                };

                let surface_caps = surface.get_capabilities(&adapter);
                let surface_format = surface_caps
                    .formats
                    .iter()
                    .copied()
                    .find(|f| f.is_srgb())
                    .unwrap_or(surface_caps.formats[0]);

                let size = window.inner_size();
                let width = if size.width > 0 { size.width } else { config.scr_width };
                let height = if size.height > 0 { size.height } else { config.scr_height };

                let surface_config = wgpu::SurfaceConfiguration {
                    usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
                    format: surface_format,
                    width,
                    height,
                    present_mode: wgpu::PresentMode::AutoVsync,
                    alpha_mode: surface_caps.alpha_modes[0],
                    view_formats: vec![],
                    desired_maximum_frame_latency: 2,
                };
                surface.configure(&device, &surface_config);

                let renderer = Renderer::new(
                    device,
                    queue,
                    surface_format,
                    width,
                    height,
                    include_str!("../shaders/shader.wgsl"),
                );

                let scene = match GltfScene::load(
                    &model_path,
                    &renderer.device,
                    &renderer.queue,
                    &renderer.bgl_obj,
                    &renderer.bgl_mat,
                    &renderer.default_view,
                    &renderer.default_sampler,
                ) {
                    Ok(s) => s,
                    Err(e) => {
                        eprintln!("[Engine-Fatal] Failed to load glTF model '{model_path}': {e:?}");
                        return;
                    }
                };

                let camera = Camera::new(
                    config.cam_pos,
                    config.cam_target,
                    config.cam_up,
                    config.cam_fov,
                    config.cam_near,
                    config.cam_far,
                );

                println!("[Engine-Run] Successfully initialized graphics pipeline and loaded model: {model_path}");
                render_state = Some(RenderState {
                    surface,
                    surface_config,
                    renderer,
                    scene,
                    camera,
                });
            }
        }
        Event::Suspended => {
            println!("[Engine-Lifecycle] Suspended event received.");
            render_state = None;
        }
        Event::WindowEvent { ref event, window_id } if window_id == window.id() => match event {
            WindowEvent::CloseRequested
            | WindowEvent::KeyboardInput {
                event:
                    KeyEvent {
                        state: ElementState::Pressed,
                        physical_key: PhysicalKey::Code(KeyCode::Escape),
                        ..
                    },
                ..
            } => target.exit(),
            WindowEvent::Resized(physical_size) => {
                if let Some(state) = render_state.as_mut() {
                    if physical_size.width > 0 && physical_size.height > 0 {
                        state.surface_config.width = physical_size.width;
                        state.surface_config.height = physical_size.height;
                        state.surface.configure(&state.renderer.device, &state.surface_config);
                        state.renderer.resize(physical_size.width, physical_size.height);
                    }
                }
            }
            WindowEvent::RedrawRequested => {
                let frame_start = Instant::now();

                if let Some(state) = render_state.as_mut() {
                    match state.surface.get_current_texture() {
                        Ok(output) => {
                            let view = output.texture.create_view(&wgpu::TextureViewDescriptor::default());
                            let aspect = state.surface_config.width as f32 / state.surface_config.height.max(1) as f32;

                            state.renderer.render_frame(
                                &view,
                                &state.camera,
                                aspect,
                                config.light_dir,
                                &state.scene,
                            );
                            output.present();
                        }
                        Err(wgpu::SurfaceError::Lost | wgpu::SurfaceError::Outdated) => {
                            state.surface.configure(&state.renderer.device, &state.surface_config);
                        }
                        Err(wgpu::SurfaceError::OutOfMemory) => {
                            eprintln!("[Engine-Fatal] GPU out of memory.");
                            target.exit();
                        }
                        Err(e) => {
                            eprintln!("[Engine-Warn] Surface error: {e:?}");
                        }
                    }
                }

                if target_frame_time > Duration::ZERO {
                    let elapsed = frame_start.elapsed();
                    if elapsed < target_frame_time {
                        std::thread::sleep(target_frame_time - elapsed);
                    }
                }

                window.request_redraw();
            }
            _ => {}
        },
        Event::AboutToWait => {
            window.request_redraw();
        }
        _ => {}
    })?;

    Ok(())
}

#[cfg(target_os = "android")]
#[no_mangle]
fn android_main(app: winit::platform::android::activity::AndroidApp) {
    use winit::platform::android::EventLoopBuilderExtAndroid;
    let event_loop = match winit::event_loop::EventLoopBuilder::new()
        .with_android_app(app)
        .build()
    {
        Ok(el) => el,
        Err(e) => {
            eprintln!("[Android-Fatal] Failed to create event loop: {e:?}");
            return;
        }
    };
    let default_model = "/sdcard/Android/data/org.antigravity.webgpurenderer/files/mclaren_p1.glb";
    if let Err(e) = run_engine(event_loop, default_model) {
        eprintln!("[Android-Fatal] Engine execution failed: {e:?}");
    }
}
// #endregion
