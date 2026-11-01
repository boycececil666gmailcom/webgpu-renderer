// #region Imports
use std::path::Path;
#[cfg(not(target_os = "android"))]
use std::path::PathBuf;
use serde::{Deserialize, Serialize};
// #endregion

// #region Types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SettingsFile {
    #[serde(default = "default_target_fps")]
    pub target_fps: u32,
    #[serde(default = "default_model_name")]
    pub model: String,
    #[serde(default = "default_env_map_name")]
    pub env_map: String,
    #[serde(default = "default_env_map_intensity")]
    pub env_map_intensity: f32,
    #[serde(default = "default_max_texture_size")]
    pub max_texture_size: u32,
    #[serde(default = "default_scatter_config_name")]
    pub scatter_config: Option<String>,
}

#[derive(Debug, Clone)]
pub struct Config {
    pub target_fps: u32,
    pub default_model: String,
    pub default_env_map: String,
    pub env_map_intensity: f32,
    pub max_texture_size: u32,
    pub scatter_config: Option<String>,
}
// #endregion

// #region Scaffolding
fn default_target_fps() -> u32 {
    60
}

fn default_model_name() -> String {
    "base_scene.glb".to_string()
}

fn default_env_map_name() -> String {
    "je_gray_02_1k.exr".to_string()
}

fn default_env_map_intensity() -> f32 {
    10.0
}

fn default_max_texture_size() -> u32 {
    4096
}

fn default_scatter_config_name() -> Option<String> {
    Some("scatter.json".to_string())
}

impl Default for SettingsFile {
    fn default() -> Self {
        Self {
            target_fps: default_target_fps(),
            model: default_model_name(),
            env_map: default_env_map_name(),
            env_map_intensity: default_env_map_intensity(),
            max_texture_size: default_max_texture_size(),
            scatter_config: default_scatter_config_name(),
        }
    }
}

impl Config {
    pub fn resolve_asset_path(raw_name: &str, _category: &str) -> String {
        #[cfg(target_os = "android")]
        {
            if raw_name.starts_with('/') {
                raw_name.to_string()
            } else {
                let file_name = Path::new(raw_name).file_name().and_then(|n| n.to_str()).unwrap_or(raw_name);
                let external = format!("/sdcard/Android/data/org.antigravity.webgpurenderer/files/{file_name}");
                let internal = format!("/data/user/0/org.antigravity.webgpurenderer/files/{file_name}");
                if Path::new(&external).exists() {
                    external
                } else if Path::new(&internal).exists() {
                    internal
                } else {
                    external
                }
            }
        }

        #[cfg(not(target_os = "android"))]
        {
            let path = Path::new(raw_name);
            if path.exists() {
                return raw_name.to_string();
            }

            let candidate = PathBuf::from(_category).join(path.file_name().unwrap_or(path.as_os_str()));
            if candidate.exists() {
                return candidate.to_string_lossy().to_string();
            }

            candidate.to_string_lossy().to_string()
        }
    }

    fn from_settings(settings: SettingsFile) -> Self {
        let default_model = Self::resolve_asset_path(&settings.model, "assets/models");
        let default_env_map = Self::resolve_asset_path(&settings.env_map, "assets/textures");
        let scatter_config = settings.scatter_config.map(|s| Self::resolve_asset_path(&s, "config"));

        Self {
            target_fps: settings.target_fps,
            default_model,
            default_env_map,
            env_map_intensity: settings.env_map_intensity,
            max_texture_size: settings.max_texture_size,
            scatter_config,
        }
    }

    fn create_default() -> Self {
        Self::from_settings(SettingsFile::default())
    }
}

impl Default for Config {
    fn default() -> Self {
        Self::create_default()
    }
}
// #endregion

// #region Core
impl Config {
    pub fn load() -> Self {
        #[cfg(target_os = "android")]
        let candidates = [
            "/sdcard/Android/data/org.antigravity.webgpurenderer/files/settings.json",
            "/sdcard/Android/data/org.antigravity.webgpurenderer/files/config/settings.json",
            "/data/user/0/org.antigravity.webgpurenderer/files/settings.json",
            "/data/user/0/org.antigravity.webgpurenderer/files/config/settings.json",
        ];

        #[cfg(not(target_os = "android"))]
        let candidates = [
            "config/settings.json",
            "settings.json",
        ];

        for path in &candidates {
            if let Ok(content) = std::fs::read_to_string(path) {
                if let Ok(settings) = serde_json::from_str::<SettingsFile>(&content) {
                    crate::preprocessing::telemetry::log_info(
                        "Config",
                        "Load",
                        &format!("Loaded settings from '{path}': model='{}', env_map='{}'", settings.model, settings.env_map),
                    );
                    return Self::from_settings(settings);
                } else {
                    crate::preprocessing::telemetry::log_warn(
                        "Config",
                        "Load",
                        &format!("Failed to parse JSON settings at '{path}', trying fallback..."),
                    );
                }
            }
        }

        crate::preprocessing::telemetry::log_info("Config", "Load", "Using default engine configuration.");
        Self::create_default()
    }
}
// #endregion

// #region Tests
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_defaults() {
        let config = Config::default();
        assert_eq!(config.target_fps, 60);
        assert_eq!(config.max_texture_size, 4096);
        assert!((config.env_map_intensity - 10.0).abs() < 1e-4);
        assert!(!config.default_model.is_empty());
    }

    #[test]
    #[cfg(not(target_os = "android"))]
    fn test_desktop_config_paths() {
        let config = Config::load();
        assert!(config.default_model.contains("base_scene.glb"));
        assert!(config.default_env_map.contains("je_gray_02_1k.exr"));
        assert!(config.scatter_config.as_deref().unwrap().contains("scatter.json"));
    }

    #[test]
    fn test_load_exr() {
        let path = "assets/textures/je_gray_02_1k.exr";
        let bytes = std::fs::read(path).expect("file exists");
        let img = image::load_from_memory(&bytes);
        assert!(img.is_ok(), "Failed to decode EXR: {:?}", img.err());
        let dyn_img = img.unwrap();
        println!("Loaded EXR dimensions: {}x{}, color type: {:?}", dyn_img.width(), dyn_img.height(), dyn_img.color());
        if let image::DynamicImage::ImageRgb32F(ref rgb32f) = dyn_img {
            let w = rgb32f.width();
            let h = rgb32f.height();
            let top_row = h / 4;
            let mid_row = h / 2;
            let bot_row = 3 * h / 4;
            let avg_row = |row: u32| -> f32 {
                let mut sum = 0.0;
                for x in 0..w {
                    let p = rgb32f.get_pixel(x, row);
                    sum += (p[0] + p[1] + p[2]) / 3.0;
                }
                sum / w as f32
            };
            println!("EXR stats: top(sky) avg={}, horizon avg={}, bot(ground) avg={}", avg_row(top_row), avg_row(mid_row), avg_row(bot_row));
        }
        let rgba8 = dyn_img.to_rgba8();
        let raw = rgba8.as_raw();
        let non_zero = raw.iter().filter(|&&v| v > 0).count();
        let min_val = raw.iter().min().unwrap();
        let max_val = raw.iter().max().unwrap();
        println!("RGBA8 len: {}, non-zero: {}, min: {}, max: {}", raw.len(), non_zero, min_val, max_val);
    }
}
// #endregion
