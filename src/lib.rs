// #region Imports
pub mod config;
pub mod gltf_loader;
pub mod material;
pub mod renderer;

pub use config::Config;
pub use gltf_loader::GltfScene;
pub use material::Material;
pub use renderer::Renderer;

use std::sync::Arc;
use std::time::{Duration, Instant};

use winit::{
    event::{Event, WindowEvent},
    event_loop::{EventLoop, EventLoopBuilder, EventLoopWindowTarget},
    platform::android::{activity::AndroidApp, EventLoopBuilderExtAndroid},
    window::{Window, WindowBuilder},
};
// #endregion

// #region Types
struct RenderState {
    surface: wgpu::Surface<'static>,
    surface_config: wgpu::SurfaceConfiguration,
    renderer: Renderer,
    scene: GltfScene,
}
// #endregion

// #region Scaffolding
fn create_android_event_loop(app: AndroidApp) -> Result<EventLoop<()>, Box<dyn std::error::Error>> {
    let event_loop = EventLoopBuilder::new().with_android_app(app).build()?;
    Ok(event_loop)
}

fn create_window(event_loop: &EventLoop<()>) -> Result<Arc<Window>, Box<dyn std::error::Error>> {
    let window = WindowBuilder::new().build(event_loop)?;
    Ok(Arc::new(window))
}

fn compute_frame_budget(target_fps: u32) -> Duration {
    if target_fps > 0 {
        Duration::from_secs_f64(1.0 / target_fps as f64)
    } else {
        Duration::ZERO
    }
}

fn init_render_state(
    window: Arc<Window>,
    instance: &wgpu::Instance,
    config: &Config,
) -> Option<RenderState> {
    println!("[Engine-Lifecycle] Android surface created. Initializing Vulkan/WebGPU...");
    let surface = match instance.create_surface(window.clone()) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("[Engine-Fatal] Failed to create WebGPU surface: {e:?}");
            return None;
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
            return None;
        }
    };

    let (device, queue) = match pollster::block_on(adapter.request_device(
        &wgpu::DeviceDescriptor {
            label: Some("WebGPU Android Device"),
            required_features: wgpu::Features::empty(),
            required_limits: wgpu::Limits::default(),
            memory_hints: Default::default(),
        },
        None,
    )) {
        Ok(pair) => pair,
        Err(e) => {
            eprintln!("[Engine-Fatal] Failed to request device: {e:?}");
            return None;
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
    let width = size.width.max(1);
    let height = size.height.max(1);

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
        &config.default_model,
        &renderer.device,
        &renderer.queue,
        &renderer.bgl_obj,
        &renderer.bgl_mat,
        &renderer.default_view,
        &renderer.default_sampler,
    ) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("[Engine-Fatal] Failed to load glTF model '{}': {e:?}", config.default_model);
            return None;
        }
    };

    println!("[Engine-Run] Graphics pipeline ready on Android. Model: {}", config.default_model);
    Some(RenderState {
        surface,
        surface_config,
        renderer,
        scene,
    })
}

fn handle_window_event(
    event: &WindowEvent,
    config: &Config,
    target: &EventLoopWindowTarget<()>,
    target_frame_time: Duration,
    state_opt: &mut Option<RenderState>,
) {
    match event {
        WindowEvent::Resized(physical_size) => {
            if let Some(state) = state_opt.as_mut() {
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

            if let Some(state) = state_opt.as_mut() {
                match state.surface.get_current_texture() {
                    Ok(output) => {
                        let view = output.texture.create_view(&wgpu::TextureViewDescriptor::default());
                        let aspect = state.surface_config.width as f32 / state.surface_config.height.max(1) as f32;
                        let view_mat = glam::Mat4::look_at_rh(config.cam_pos, config.cam_target, config.cam_up);
                        let proj_mat = glam::Mat4::perspective_rh(config.cam_fov.to_radians(), aspect, config.cam_near, config.cam_far);

                        state.renderer.render_frame(
                            &view,
                            view_mat,
                            proj_mat,
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
        }
        _ => {}
    }
}

fn handle_engine_event(
    event: Event<()>,
    target: &EventLoopWindowTarget<()>,
    window: &Arc<Window>,
    instance: &wgpu::Instance,
    config: &Config,
    target_frame_time: Duration,
    render_state: &mut Option<RenderState>,
) {
    match event {
        Event::Resumed => {
            if render_state.is_none() {
                *render_state = init_render_state(window.clone(), instance, config);
            }
        }
        Event::Suspended => {
            println!("[Engine-Lifecycle] Suspended event received. Dropping surface...");
            *render_state = None;
        }
        Event::WindowEvent { ref event, window_id } if window_id == window.id() => {
            handle_window_event(event, config, target, target_frame_time, render_state);
        }
        Event::AboutToWait => {
            window.request_redraw();
        }
        _ => {}
    }
}
// #endregion

// #region Core
#[no_mangle]
pub fn android_main(app: AndroidApp) {
    let config = Config::load();
    let event_loop = match create_android_event_loop(app) {
        Ok(el) => el,
        Err(e) => return eprintln!("[Android-Fatal] Failed to create event loop: {e:?}"),
    };
    if let Err(e) = run_engine(event_loop, config) {
        eprintln!("[Android-Fatal] Engine execution failed: {e:?}");
    }
}

pub fn run_engine(event_loop: EventLoop<()>, config: Config) -> Result<(), Box<dyn std::error::Error>> {
    let window = create_window(&event_loop)?;
    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
        backends: wgpu::Backends::PRIMARY,
        ..Default::default()
    });
    let target_frame_time = compute_frame_budget(config.target_fps);
    let mut render_state: Option<RenderState> = None;

    event_loop.run(move |event, target| {
        handle_engine_event(event, target, &window, &instance, &config, target_frame_time, &mut render_state);
    })?;

    Ok(())
}
// #endregion
