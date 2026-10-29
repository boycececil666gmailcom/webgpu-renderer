// #region Imports
use std::env;
use std::process::ExitCode;
use webgpu_engine::{create_event_loop, run_engine, Config};
// #endregion

// #region Types
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ViewerCommand {
    Run { model_path: Option<String> },
    Help,
}
// #endregion

// #region Scaffolding
pub fn parse_args(args: &[String]) -> ViewerCommand {
    match args.get(1).map(|s| s.trim()) {
        Some("-h" | "--help" | "-?" | "/?") => ViewerCommand::Help,
        Some(path) if !path.is_empty() => ViewerCommand::Run {
            model_path: Some(path.to_string()),
        },
        _ => ViewerCommand::Run { model_path: None },
    }
}

pub fn apply_command_to_config(mut config: Config, cmd: &ViewerCommand) -> Config {
    if let ViewerCommand::Run { model_path: Some(ref model) } = cmd {
        config.default_model = model.clone();
    }
    config
}

fn print_usage() {
    println!("WebGPU Desktop Viewer");
    println!("Usage: webgpu-viewer [MODEL_PATH.glb]");
    println!("  <MODEL_PATH>  Optional path to glTF/GLB model (defaults to gltf/base_scene.glb)");
    println!("  -h, --help    Show this help message");
}
// #endregion

// #region Core
fn launch_viewer(cmd: ViewerCommand) -> Result<(), Box<dyn std::error::Error>> {
    match cmd {
        ViewerCommand::Help => {
            print_usage();
            Ok(())
        }
        ViewerCommand::Run { ref model_path } => {
            if let Some(ref path) = model_path {
                if !std::path::Path::new(path).exists() {
                    return Err(format!("Model file not found: {path}").into());
                }
            }
            let base_config = Config::load();
            let config = apply_command_to_config(base_config, &cmd);
            let event_loop = create_event_loop()?;
            run_engine(event_loop, config)
        }
    }
}
// #endregion

// #region Main
fn main() -> ExitCode {
    let raw_args: Vec<String> = env::args().collect();
    let cmd = parse_args(&raw_args);

    match launch_viewer(cmd) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("[webgpu-viewer] Error: {e}");
            ExitCode::FAILURE
        }
    }
}
// #endregion

// #region Tests
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_args_empty() {
        let args = vec!["webgpu-viewer".to_string()];
        let cmd = parse_args(&args);
        assert_eq!(cmd, ViewerCommand::Run { model_path: None });
    }

    #[test]
    fn test_parse_args_whitespace_empty() {
        let args = vec!["webgpu-viewer".to_string(), "   ".to_string()];
        let cmd = parse_args(&args);
        assert_eq!(cmd, ViewerCommand::Run { model_path: None });
    }

    #[test]
    fn test_parse_args_with_model() {
        let args = vec!["webgpu-viewer".to_string(), "gltf/tree_01_lod1.glb".to_string()];
        let cmd = parse_args(&args);
        assert_eq!(
            cmd,
            ViewerCommand::Run {
                model_path: Some("gltf/tree_01_lod1.glb".to_string())
            }
        );
    }

    #[test]
    fn test_parse_args_help() {
        let args = vec!["webgpu-viewer".to_string(), "--help".to_string()];
        let cmd = parse_args(&args);
        assert_eq!(cmd, ViewerCommand::Help);

        let args_win = vec!["webgpu-viewer".to_string(), "/?".to_string()];
        assert_eq!(parse_args(&args_win), ViewerCommand::Help);
    }

    #[test]
    fn test_apply_command_to_config() {
        let config = Config::default();
        let cmd = ViewerCommand::Run {
            model_path: Some("custom/test.glb".to_string()),
        };
        let updated = apply_command_to_config(config, &cmd);
        assert_eq!(updated.default_model, "custom/test.glb");
    }

    #[test]
    fn test_launch_viewer_nonexistent_model() {
        let cmd = ViewerCommand::Run {
            model_path: Some("nonexistent_dir/does_not_exist_xyz.glb".to_string()),
        };
        let result = launch_viewer(cmd);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("Model file not found"));
    }
}
// #endregion
