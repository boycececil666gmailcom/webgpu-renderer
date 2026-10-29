// #region Imports
// No external imports required
// #endregion

// #region Types
#[derive(Debug, Clone)]
pub struct Config {
    pub target_fps: u32,
    pub default_model: String,
    pub default_env_map: String,
    pub max_texture_size: u32,
    pub scatter_config: Option<String>,
}
// #endregion

// #region Scaffolding
impl Config {
    fn create_default() -> Self {
        Self {
            target_fps: 60,
            default_model: "/sdcard/Android/data/org.antigravity.webgpurenderer/files/base_scene.glb".to_string(),
            default_env_map: "/sdcard/Android/data/org.antigravity.webgpurenderer/files/autumn_forest_01_1k.png".to_string(),
            max_texture_size: 4096,
            scatter_config: Some("/sdcard/Android/data/org.antigravity.webgpurenderer/files/scatter.json".to_string()),
        }
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
        let cfg = Self::create_default();
        crate::preprocessing::telemetry::log_info("Config", "Load", "Engine configuration initialized.");
        cfg
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
        assert!(!config.default_model.is_empty());
    }
}
// #endregion
