// #region Config
use glam::Vec3;
use std::env;
use std::str::FromStr;

#[derive(Debug, Clone)]
pub struct Config {
    pub scr_width: u32,
    pub scr_height: u32,
    pub target_fps: u32,
    pub cam_pos: Vec3,
    pub cam_target: Vec3,
    pub cam_up: Vec3,
    pub cam_fov: f32,
    pub cam_near: f32,
    pub cam_far: f32,
    pub light_dir: Vec3,
}

fn env_var<T: FromStr>(key: &str, default: T) -> T {
    env::var(key).ok().and_then(|v| v.parse().ok()).unwrap_or(default)
}

impl Config {
    pub fn load() -> Self {
        dotenvy::dotenv().ok();

        let cfg = Self {
            scr_width: env_var("SCR_WIDTH", 1920),
            scr_height: env_var("SCR_HEIGHT", 1080),
            target_fps: env_var("TARGET_FPS", 165),
            cam_pos: Vec3::new(
                env_var("CAM_POS_X", 1.75),
                env_var("CAM_POS_Y", 0.82),
                env_var("CAM_POS_Z", 5.35),
            ),
            cam_target: Vec3::new(
                env_var("CAM_TARGET_X", 0.0),
                env_var("CAM_TARGET_Y", 0.48),
                env_var("CAM_TARGET_Z", 1.20),
            ),
            cam_up: Vec3::new(0.0, 1.0, 0.0),
            cam_fov: env_var("CAM_FOV", 28.0),
            cam_near: env_var("CAM_NEAR", 0.1),
            cam_far: env_var("CAM_FAR", 500.0),
            light_dir: Vec3::new(
                env_var("LIGHT_DIR_X", 0.3),
                env_var("LIGHT_DIR_Y", 1.0),
                env_var("LIGHT_DIR_Z", 0.5),
            ),
        };

        println!("[Config-Load] Configuration successfully initialized.");
        cfg
    }
}
// #endregion
