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
}
// #endregion

// #region Scaffolding
impl Config {
    fn create_default() -> Self {
        Self {
            target_fps: 60,
            default_model: "/sdcard/Android/data/org.antigravity.webgpurenderer/files/base_scene.glb".to_string(),
            default_env_map: "/sdcard/Android/data/org.antigravity.webgpurenderer/files/autumn_forest_01_1k.png".to_string(),
            max_texture_size: 2048,
        }
    }
}
// #endregion

// #region Core
impl Config {
    pub fn load() -> Self {
        let cfg = Self::create_default();
        crate::telemetry::log_info("Config", "Load", "Engine configuration initialized.");
        cfg
    }
}
// #endregion
