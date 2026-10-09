// #region Main
use std::env;
use std::path::Path;
use winit::event_loop::EventLoop;

fn main() -> Result<(), Box<dyn std::error::Error>> {
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

    let event_loop = EventLoop::new()?;
    webgpu_engine::run_engine(event_loop, &model_path)
}
// #endregion
