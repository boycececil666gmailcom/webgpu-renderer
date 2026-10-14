// #region Imports
use glam::Vec3;
// #endregion

// #region Types
#[derive(Debug, Clone)]
pub struct Config {
    pub target_fps: u32,
    pub cam_pos: Vec3,
    pub cam_target: Vec3,
    pub cam_up: Vec3,
    pub cam_fov: f32,
    pub cam_near: f32,
    pub cam_far: f32,
    pub light_dir: Vec3,
    pub default_model: String,
}
// #endregion

// #region Scaffolding
impl Config {
    fn create_default() -> Self {
        Self {
            target_fps: 60,
            cam_pos: Vec3::new(1.75, 0.82, 5.35),
            cam_target: Vec3::new(0.0, 0.48, 1.20),
            cam_up: Vec3::new(0.0, 1.0, 0.0),
            cam_fov: 28.0,
            cam_near: 0.1,
            cam_far: 500.0,
            light_dir: Vec3::new(0.3, 1.0, 0.5),
            default_model: "/sdcard/Android/data/org.antigravity.webgpurenderer/files/mclaren_p1.glb".to_string(),
        }
    }
}
// #endregion

// #region Core
impl Config {
    pub fn load() -> Self {
        let cfg = Self::create_default();
        println!("[Config-Load] Android configuration initialized.");
        cfg
    }
}
// #endregion
