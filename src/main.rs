// #region Main
use std::env;
use std::path::Path;
use std::sync::Arc;
use std::time::{Duration, Instant};

use winit::{
    dpi::PhysicalSize,
    event::{ElementState, Event, KeyEvent, WindowEvent},
    event_loop::EventLoop,
    keyboard::{KeyCode, PhysicalKey},
    window::WindowBuilder,
};

use webgpu_engine::{Camera, Config, GltfScene, Renderer};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. Resolve 3D model glTF/GLB file path argument
    let args: Vec<String> = env::args().collect();
    let model_path = if args.len() > 1 {
        args[1].clone()
    } else {
        let default_local = "gltf/mclaren_p1.glb";
        let default_parent = "../webgpu-renderer/gltf/mclaren_p1.glb";
        if Path::new(default_local).exists() {
            default_local.to_string()
        } else if Path::new(default_parent).exists() {
            default_parent.to_string()
        } else {
            println!("[Main-Run] Usage: webgpu-renderer <path_to_gltf_file>");
            std::process::exit(1);
        }
    };

    if !Path::new(&model_path).exists() {
        eprintln!("[Main-Run] Error: Model file '{model_path}' not found.");
        std::process::exit(1);
    }

    // 2. Load configuration and initialize window
    let config = Config::load();
    let event_loop = EventLoop::new()?;
    let window = Arc::new(
        WindowBuilder::new()
            .with_title("Antigravity WebGPU Engine (Rust)")
            .with_inner_size(PhysicalSize::new(config.scr_width, config.scr_height))
            .build(&event_loop)?,
    );

    // 3. Initialize WebGPU Surface and Hardware Device
    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
        backends: wgpu::Backends::PRIMARY,
        ..Default::default()
    });

    let surface = instance.create_surface(window.clone())?;
    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::HighPerformance,
        compatible_surface: Some(&surface),
        force_fallback_adapter: false,
    }))
    .ok_or("Failed to find suitable GPU adapter")?;

    let (device, queue) = pollster::block_on(adapter.request_device(
        &wgpu::DeviceDescriptor {
            label: Some("WebGPU Device"),
            required_features: wgpu::Features::empty(),
            required_limits: wgpu::Limits::default(),
            memory_hints: Default::default(),
        },
        None,
    ))?;

    let surface_caps = surface.get_capabilities(&adapter);
    let surface_format = surface_caps
        .formats
        .iter()
        .copied()
        .find(|f| f.is_srgb())
        .unwrap_or(surface_caps.formats[0]);

    let mut surface_config = wgpu::SurfaceConfiguration {
        usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
        format: surface_format,
        width: config.scr_width,
        height: config.scr_height,
        present_mode: wgpu::PresentMode::AutoVsync,
        alpha_mode: surface_caps.alpha_modes[0],
        view_formats: vec![],
        desired_maximum_frame_latency: 2,
    };
    surface.configure(&device, &surface_config);

    // 4. Load WGSL shader and initialize Renderer
    let shader_path = Path::new("shaders/shader.wgsl");
    let shader_source = if shader_path.exists() {
        std::fs::read_to_string(shader_path).unwrap_or_else(|_| include_str!("../shaders/shader.wgsl").to_string())
    } else {
        include_str!("../shaders/shader.wgsl").to_string()
    };

    let mut renderer = Renderer::new(
        device,
        queue,
        surface_format,
        config.scr_width,
        config.scr_height,
        &shader_source,
    );

    // 5. Load glTF 2.0 Scene & Camera
    let scene = GltfScene::load(
        &model_path,
        &renderer.device,
        &renderer.queue,
        &renderer.bgl_obj,
        &renderer.bgl_mat,
        &renderer.default_view,
        &renderer.default_sampler,
    )?;

    let camera = Camera::new(
        config.cam_pos,
        config.cam_target,
        config.cam_up,
        config.cam_fov,
        config.cam_near,
        config.cam_far,
    );

    println!("[Main-Run] Loaded Native glTF 2.0: {model_path}");
    println!("[Main-Run] Target Frame Rate: {} FPS", config.target_fps);

    let target_frame_time = if config.target_fps > 0 {
        Duration::from_secs_f64(1.0 / config.target_fps as f64)
    } else {
        Duration::ZERO
    };

    // 6. Main Event and Render Loop
    event_loop.run(move |event, target| match event {
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
                if physical_size.width > 0 && physical_size.height > 0 {
                    surface_config.width = physical_size.width;
                    surface_config.height = physical_size.height;
                    surface.configure(&renderer.device, &surface_config);
                    renderer.resize(physical_size.width, physical_size.height);
                }
            }
            WindowEvent::RedrawRequested => {
                let frame_start = Instant::now();

                match surface.get_current_texture() {
                    Ok(output) => {
                        let view = output.texture.create_view(&wgpu::TextureViewDescriptor::default());
                        let aspect = surface_config.width as f32 / surface_config.height.max(1) as f32;

                        renderer.render_frame(&view, &camera, aspect, config.light_dir, &scene);
                        output.present();
                    }
                    Err(wgpu::SurfaceError::Lost | wgpu::SurfaceError::Outdated) => {
                        surface.configure(&renderer.device, &surface_config);
                    }
                    Err(wgpu::SurfaceError::OutOfMemory) => {
                        eprintln!("[Main-Fatal] GPU out of memory.");
                        target.exit();
                    }
                    Err(e) => {
                        eprintln!("[Main-Warn] Surface error: {e:?}");
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
// #endregion
