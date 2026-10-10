// #region Main
use std::env;
use winit::event_loop::EventLoop;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let model_path = env::args().nth(1).unwrap_or_else(|| "gltf/mclaren_p1.glb".to_string());
    let event_loop = EventLoop::new()?;
    webgpu_engine::run_engine(event_loop, &model_path)
}
// #endregion
