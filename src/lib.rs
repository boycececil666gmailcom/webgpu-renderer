// #region Imports
pub mod config;
pub mod gltf_loader;
pub mod material;
pub mod renderer;
pub mod telemetry;

pub use config::Config;
pub use gltf_loader::GltfScene;
pub use material::Material;
pub use renderer::Renderer;
pub use telemetry::{log_error, log_info, log_warn, TelemetryTracker};

use std::sync::mpsc::{self, Receiver, TryRecvError};
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
    scene: Option<GltfScene>,
    scene_rx: Option<Receiver<Result<GltfScene, String>>>,
    telemetry: TelemetryTracker,
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

fn spawn_scene_load(
    renderer: &Renderer,
    model: String,
    max_texture_size: u32,
) -> Option<Receiver<Result<GltfScene, String>>> {
    let device = Arc::clone(&renderer.device);
    let queue = Arc::clone(&renderer.queue);
    let bgl_obj = Arc::clone(&renderer.bgl_obj);
    let bgl_mat = Arc::clone(&renderer.bgl_mat);
    let default_view = Arc::clone(&renderer.default_view);
    let default_sampler = Arc::clone(&renderer.default_sampler);
    let (tx, rx) = mpsc::channel();

    let spawned = std::thread::Builder::new()
        .name("scene-loader".to_string())
        .spawn(move || {
            let result = GltfScene::load(
                &model,
                &device,
                &queue,
                &bgl_obj,
                &bgl_mat,
                &default_view,
                &default_sampler,
                max_texture_size,
            )
            .map_err(|error| format!("{error:?}"));
            let _ = tx.send(result);
        });

    match spawned {
        Ok(_) => Some(rx),
        Err(error) => {
            log_error("Engine", "Load", &format!("Failed to spawn scene loader thread: {error:?}"));
            None
        }
    }
}

fn take_loaded_scene(state: &mut RenderState) {
    let Some(receiver) = state.scene_rx.as_ref() else {
        return;
    };

    match receiver.try_recv() {
        Ok(Ok(scene)) => {
            let primitive_count: usize = scene.primitives_by_mesh.iter().map(|primitives| primitives.len()).sum();
            state.telemetry.set_scene_stats(
                scene.primitives_by_mesh.len(),
                scene.render_nodes.len(),
                primitive_count,
                scene.materials.len(),
            );
            log_info("Engine", "Load", &format!(
                "Scene ready: {} meshes | {} instances | {} materials",
                scene.primitives_by_mesh.len(), scene.render_nodes.len(), scene.materials.len()
            ));
            state.scene = Some(scene);
            state.scene_rx = None;
        }
        Ok(Err(error)) => {
            log_error("Engine", "Load", &format!("Failed to load glTF model: {error}"));
            state.scene_rx = None;
        }
        Err(TryRecvError::Disconnected) => {
            log_error("Engine", "Load", "Scene loader thread terminated without producing a result.");
            state.scene_rx = None;
        }
        Err(TryRecvError::Empty) => {}
    }
}

fn init_render_state(
    window: Arc<Window>,
    instance: &wgpu::Instance,
    config: &Config,
) -> Option<RenderState> {
    log_info("Engine", "Lifecycle", "Android surface acquired. Initializing Vulkan/WebGPU device...");
    let surface = match instance.create_surface(window.clone()) {
        Ok(s) => s,
        Err(e) => {
            log_error("Engine", "Fatal", &format!("Failed to create WebGPU surface: {e:?}"));
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
            log_error("Engine", "Fatal", "Failed to find suitable GPU adapter");
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
            log_error("Engine", "Fatal", &format!("Failed to request device: {e:?}"));
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
        include_str!("../shaders/standard_pbr.wgsl"),
        &config.default_env_map,
    );

    let scene_rx = spawn_scene_load(&renderer, config.default_model.clone(), config.max_texture_size)?;

    let mut telemetry = TelemetryTracker::new();
    telemetry.set_resolution(width, height);

    log_info("Engine", "Lifecycle", &format!(
        "Pipeline ready: {}x{} ({:?}). Streaming '{}' on background thread (max texture {}px).",
        width, height, surface_format, config.default_model, config.max_texture_size
    ));

    Some(RenderState {
        surface,
        surface_config,
        renderer,
        scene: None,
        scene_rx: Some(scene_rx),
        telemetry,
    })
}

fn handle_window_event(
    event: &WindowEvent,
    _config: &Config,
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
                    state.telemetry.set_resolution(physical_size.width, physical_size.height);
                    log_info("Engine", "Lifecycle", &format!("Surface resized: {}x{}", physical_size.width, physical_size.height));
                }
            }
        }
        WindowEvent::RedrawRequested => {
            let frame_start = Instant::now();

            if let Some(state) = state_opt.as_mut() {
                take_loaded_scene(state);
                let RenderState { surface, surface_config, renderer, scene, telemetry, .. } = state;

                match surface.get_current_texture() {
                    Ok(output) => {
                        let view = output.texture.create_view(&wgpu::TextureViewDescriptor::default());
                        let aspect = surface_config.width as f32 / surface_config.height.max(1) as f32;

                        if let Some(scene) = scene.as_ref() {
                            renderer.render_frame(
                                &view,
                                scene.camera.view_matrix(),
                                scene.camera.projection_matrix(aspect),
                                &scene.light,
                                scene.camera.position(),
                                scene,
                            );
                        } else {
                            renderer.render_clear(&view);
                        }

                        output.present();
                        telemetry.record_frame(frame_start.elapsed());
                    }
                    Err(wgpu::SurfaceError::Lost | wgpu::SurfaceError::Outdated) => {
                        surface.configure(&renderer.device, surface_config);
                    }
                    Err(wgpu::SurfaceError::OutOfMemory) => {
                        log_error("Engine", "Fatal", "GPU out of memory.");
                        target.exit();
                    }
                    Err(e) => {
                        log_warn("Engine", "Surface", &format!("Surface error: {e:?}"));
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
                log_info("Engine", "Lifecycle", "Resumed event received. Acquiring surface...");
                *render_state = init_render_state(window.clone(), instance, config);
            }
        }
        Event::Suspended => {
            log_info("Engine", "Lifecycle", "Suspended event received. Dropping surface to conserve resources.");
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
        Err(e) => return log_error("Android", "Fatal", &format!("Failed to create event loop: {e:?}")),
    };
    if let Err(e) = run_engine(event_loop, config) {
        log_error("Android", "Fatal", &format!("Engine execution failed: {e:?}"));
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
