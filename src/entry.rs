// #region Imports
use std::sync::mpsc::{self, Receiver, TryRecvError};
use std::sync::Arc;
use std::time::{Duration, Instant};

#[cfg(target_os = "android")]
use winit::event_loop::EventLoopBuilder;
#[cfg(target_os = "android")]
use winit::platform::android::{activity::AndroidApp, EventLoopBuilderExtAndroid};
use winit::{
    event::{ElementState, Event, KeyEvent, WindowEvent},
    event_loop::{EventLoop, EventLoopWindowTarget},
    keyboard::{Key, NamedKey},
    window::{Window, WindowBuilder},
};

use crate::config::Config;
use crate::preprocessing::gltf_loader::GltfScene;
use crate::preprocessing::telemetry::{log_error, log_info, log_warn, TelemetryTracker};
use crate::gpu_execution::renderer::Renderer;
use crate::post_processing::postprocess::PostProcessor;
use crate::swapchain::Swapchain;
// #endregion

// #region Types
struct RenderState {
    swapchain: Swapchain,
    renderer: Renderer,
    scene: Option<GltfScene>,
    scene_rx: Option<Receiver<Result<GltfScene, String>>>,
    telemetry: TelemetryTracker,
    post_processor: PostProcessor,
}
// #endregion

// #region Scaffolding
#[cfg(target_os = "android")]
fn create_android_event_loop(app: AndroidApp) -> Result<EventLoop<()>, Box<dyn std::error::Error>> {
    let event_loop = EventLoopBuilder::new().with_android_app(app).build()?;
    Ok(event_loop)
}

pub fn create_event_loop() -> Result<EventLoop<()>, Box<dyn std::error::Error>> {
    #[cfg(target_os = "android")]
    {
        Err("Direct binary execution is not supported on Android; use android_main with NativeActivity.".into())
    }
    #[cfg(not(target_os = "android"))]
    {
        let event_loop = EventLoop::new()?;
        Ok(event_loop)
    }
}

fn create_window(event_loop: &EventLoop<()>) -> Result<Arc<Window>, Box<dyn std::error::Error>> {
    let builder = WindowBuilder::new().with_title("WebGPU Viewer");
    #[cfg(not(target_os = "android"))]
    let builder = builder.with_inner_size(winit::dpi::LogicalSize::new(1280.0, 720.0));
    let window = builder.build(event_loop)?;
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
    scatter_config: Option<String>,
    max_texture_size: u32,
) -> Option<Receiver<Result<GltfScene, String>>> {
    let device = Arc::clone(&renderer.device);
    let queue = Arc::clone(&renderer.queue);
    let bgl_mat = Arc::clone(&renderer.bgl_mat);
    let default_view = Arc::clone(&renderer.default_view);
    let default_sampler = Arc::clone(&renderer.default_sampler);
    let (tx, rx) = mpsc::channel();

    let spawned = std::thread::Builder::new()
        .name("scene-loader".to_string())
        .spawn(move || {
            let result = GltfScene::load(
                &model,
                scatter_config.as_deref(),
                &device,
                &queue,
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
    log_info("Engine", "Lifecycle", "Surface acquired. Initializing WebGPU device...");
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
            label: Some("WebGPU Device"),
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

    let size = window.inner_size();
    let swapchain = Swapchain::from_surface(surface, &adapter, &device, size.width, size.height);
    let surface_format = swapchain.format();
    let width = swapchain.config.width;
    let height = swapchain.config.height;

    let renderer = Renderer::new(
        device,
        queue,
        surface_format,
        width,
        height,
        include_str!("../shaders/standard_pbr.wgsl"),
        &config.default_env_map,
    );

    let scene_rx = spawn_scene_load(&renderer, config.default_model.clone(), config.scatter_config.clone(), config.max_texture_size)?;

    let mut telemetry = TelemetryTracker::new();
    telemetry.set_resolution(width, height);

    log_info("Engine", "Lifecycle", &format!(
        "Pipeline ready: {}x{} ({:?}). Streaming '{}' on background thread (max texture {}px).",
        width, height, surface_format, config.default_model, config.max_texture_size
    ));

    Some(RenderState {
        swapchain,
        renderer,
        scene: None,
        scene_rx: Some(scene_rx),
        telemetry,
        post_processor: PostProcessor::new(),
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
                    state.swapchain.resize(&state.renderer.device, physical_size.width, physical_size.height);
                    state.renderer.resize(physical_size.width, physical_size.height);
                    state.telemetry.set_resolution(physical_size.width, physical_size.height);
                }
            }
        }
        WindowEvent::RedrawRequested => {
            let frame_start = Instant::now();

            if let Some(state) = state_opt.as_mut() {
                take_loaded_scene(state);
                let RenderState {
                    swapchain,
                    renderer,
                    scene,
                    telemetry,
                    post_processor,
                    ..
                } = state;

                match swapchain.acquire_frame() {
                    Ok(output) => {
                        let view = output.texture.create_view(&wgpu::TextureViewDescriptor::default());
                        let aspect = swapchain.aspect_ratio();

                        // Step 1: Pre-processing (CPU-centered scene preparation, frustum/LOD culling)
                        if let Some(scene) = scene.as_mut() {
                            scene.update_lods(&renderer.queue, scene.camera.position(), aspect, scene.camera.yfov);

                            // Step 2: GPU Execution (GPU draw calls and rasterization pass)
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

                        // Step 3: Post-processing (Image-space passes, tone mapping, compositing)
                        if post_processor.is_enabled() {
                            let mut post_encoder = renderer.device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
                                label: Some("Post-Processing Encoder"),
                            });
                            post_processor.process(&mut post_encoder, &view, &view);
                            let submission = renderer.queue.submit(std::iter::once(post_encoder.finish()));
                            renderer.device.poll(wgpu::Maintain::WaitForSubmissionIndex(submission));
                        }

                        // Step 4: Presentation (Swapchain present and display metrics)
                        swapchain.present_frame(output);
                        telemetry.record_frame(frame_start.elapsed());
                    }
                    Err(wgpu::SurfaceError::Lost | wgpu::SurfaceError::Outdated) => {
                        swapchain.reconfigure(&renderer.device);
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
        WindowEvent::KeyboardInput {
            event:
                KeyEvent {
                    logical_key: Key::Named(NamedKey::Escape),
                    state: ElementState::Pressed,
                    ..
                },
            ..
        } => {
            target.exit();
        }
        WindowEvent::CloseRequested => {
            target.exit();
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
    is_suspended: &mut bool,
) {
    match event {
        Event::Resumed => {
            *is_suspended = false;
            if render_state.is_none() {
                log_info("Engine", "Lifecycle", "Resumed event received. Acquiring surface...");
                *render_state = init_render_state(window.clone(), instance, config);
                if render_state.is_none() {
                    log_error("Engine", "Fatal", "Failed to initialize render state on resume; terminating.");
                    target.exit();
                }
            }
        }
        Event::Suspended => {
            log_info("Engine", "Lifecycle", "Suspended event received. Dropping surface to conserve resources.");
            *is_suspended = true;
            *render_state = None;
        }
        Event::WindowEvent { ref event, window_id } if window_id == window.id() => {
            handle_window_event(event, config, target, target_frame_time, render_state);
        }
        Event::AboutToWait => {
            #[cfg(not(target_os = "android"))]
            if !*is_suspended && render_state.is_none() {
                log_info("Engine", "Lifecycle", "Acquiring surface on desktop event loop start...");
                *render_state = init_render_state(window.clone(), instance, config);
                if render_state.is_none() {
                    log_error("Engine", "Fatal", "Failed to initialize render state on desktop start; terminating.");
                    target.exit();
                }
            }
            if render_state.is_some() {
                window.request_redraw();
            }
        }
        _ => {}
    }
}
// #endregion

// #region Core
#[cfg(target_os = "android")]
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
    let mut is_suspended = false;

    event_loop.run(move |event, target| {
        handle_engine_event(
            event,
            target,
            &window,
            &instance,
            &config,
            target_frame_time,
            &mut render_state,
            &mut is_suspended,
        );
    })?;

    Ok(())
}
// #endregion

