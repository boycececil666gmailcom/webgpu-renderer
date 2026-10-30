use webgpu_engine::{GltfScene, Renderer};

#[test]
fn test_render_capture_frame() {
    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
        backends: wgpu::Backends::PRIMARY,
        ..Default::default()
    });
    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::HighPerformance,
        compatible_surface: None,
        force_fallback_adapter: false,
    }));
    let Some(adapter) = adapter else {
        eprintln!("No GPU adapter available for test_render_capture_frame");
        return;
    };

    let (device, queue) = pollster::block_on(adapter.request_device(
        &wgpu::DeviceDescriptor {
            label: Some("Test Device"),
            required_features: wgpu::Features::empty(),
            required_limits: wgpu::Limits::default(),
            memory_hints: Default::default(),
        },
        None,
    ))
    .expect("Failed to create test device");

    let (width, height) = (1280u32, 720u32);
    let target_texture = device.create_texture(&wgpu::TextureDescriptor {
        label: Some("Capture Texture"),
        size: wgpu::Extent3d {
            width,
            height,
            depth_or_array_layers: 1,
        },
        mip_level_count: 1,
        sample_count: 1,
        dimension: wgpu::TextureDimension::D2,
        format: wgpu::TextureFormat::Rgba8UnormSrgb,
        usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
        view_formats: &[],
    });

    let target_view = target_texture.create_view(&wgpu::TextureViewDescriptor::default());
    let mut renderer = Renderer::new(
        device,
        queue,
        wgpu::TextureFormat::Rgba8UnormSrgb,
        width,
        height,
        include_str!("../shaders/standard_pbr.wgsl"),
        "assets/textures/autumn_forest_01_1k.png",
    );

    let mut scene = GltfScene::load(
        "assets/models/base_scene.glb",
        Some("config/scatter.json"),
        &renderer.device,
        &renderer.queue,
        &renderer.bgl_mat,
        &renderer.default_view,
        &renderer.default_sampler,
        4096,
    )
    .expect("Failed to load scene");

    let aspect = width as f32 / height as f32;
    scene.update_lods(&renderer.queue, scene.camera.position(), aspect, scene.camera.yfov);

    renderer.render_frame(
        &target_view,
        scene.camera.view_matrix(),
        scene.camera.projection_matrix(aspect),
        &scene.light,
        scene.camera.position(),
        &scene,
    );

    // Read back buffer
    let bytes_per_pixel = 4u32;
    let unpadded_bytes_per_row = width * bytes_per_pixel;
    let align = wgpu::COPY_BYTES_PER_ROW_ALIGNMENT;
    let padded_bytes_per_row = (unpadded_bytes_per_row + align - 1) / align * align;
    let buffer_size = (padded_bytes_per_row * height) as wgpu::BufferAddress;

    let readback_buffer = renderer.device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("Readback Buffer"),
        size: buffer_size,
        usage: wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST,
        mapped_at_creation: false,
    });

    let mut encoder = renderer.device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
        label: Some("Readback Encoder"),
    });

    encoder.copy_texture_to_buffer(
        wgpu::ImageCopyTexture {
            texture: &target_texture,
            mip_level: 0,
            origin: wgpu::Origin3d::ZERO,
            aspect: wgpu::TextureAspect::All,
        },
        wgpu::ImageCopyBuffer {
            buffer: &readback_buffer,
            layout: wgpu::ImageDataLayout {
                offset: 0,
                bytes_per_row: Some(padded_bytes_per_row),
                rows_per_image: Some(height),
            },
        },
        wgpu::Extent3d {
            width,
            height,
            depth_or_array_layers: 1,
        },
    );

    renderer.queue.submit(std::iter::once(encoder.finish()));

    let buffer_slice = readback_buffer.slice(..);
    let (tx, rx) = std::sync::mpsc::channel();
    buffer_slice.map_async(wgpu::MapMode::Read, move |res| {
        let _ = tx.send(res);
    });

    renderer.device.poll(wgpu::Maintain::Wait);
    rx.recv().expect("Failed to receive map result").expect("Buffer mapping failed");

    let mapped = buffer_slice.get_mapped_range();
    let mut image_data = Vec::with_capacity((width * height * 4) as usize);
    for row in 0..height {
        let start = (row * padded_bytes_per_row) as usize;
        let end = start + unpadded_bytes_per_row as usize;
        image_data.extend_from_slice(&mapped[start..end]);
    }
    drop(mapped);
    readback_buffer.unmap();

    image::save_buffer(
        "current_render.png",
        &image_data,
        width,
        height,
        image::ExtendedColorType::Rgba8,
    )
    .expect("Failed to save capture image");

    println!("Saved current_render.png successfully! Dimensions: {width}x{height}");
}
