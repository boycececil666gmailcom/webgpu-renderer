// #region Config
use std::env;
use glam::Vec3;

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

impl Config {
    pub fn load() -> Self {
        dotenvy::dotenv().ok();

        let scr_width = env::var("SCR_WIDTH")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(1920);
        let scr_height = env::var("SCR_HEIGHT")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(1080);
        let target_fps = env::var("TARGET_FPS")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(165);

        let cam_pos = Vec3::new(
            env::var("CAM_POS_X").ok().and_then(|v| v.parse().ok()).unwrap_or(1.75),
            env::var("CAM_POS_Y").ok().and_then(|v| v.parse().ok()).unwrap_or(0.82),
            env::var("CAM_POS_Z").ok().and_then(|v| v.parse().ok()).unwrap_or(5.35),
        );

        let cam_target = Vec3::new(
            env::var("CAM_TARGET_X").ok().and_then(|v| v.parse().ok()).unwrap_or(0.0),
            env::var("CAM_TARGET_Y").ok().and_then(|v| v.parse().ok()).unwrap_or(0.48),
            env::var("CAM_TARGET_Z").ok().and_then(|v| v.parse().ok()).unwrap_or(1.20),
        );

        let cam_up = Vec3::new(0.0, 1.0, 0.0);

        let cam_fov = env::var("CAM_FOV")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(28.0);
        let cam_near = env::var("CAM_NEAR")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(0.1);
        let cam_far = env::var("CAM_FAR")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(500.0);

        let light_dir = Vec3::new(
            env::var("LIGHT_DIR_X").ok().and_then(|v| v.parse().ok()).unwrap_or(0.3),
            env::var("LIGHT_DIR_Y").ok().and_then(|v| v.parse().ok()).unwrap_or(1.0),
            env::var("LIGHT_DIR_Z").ok().and_then(|v| v.parse().ok()).unwrap_or(0.5),
        );

        println!("[Config-Load] Configuration successfully initialized.");

        Self {
            scr_width,
            scr_height,
            target_fps,
            cam_pos,
            cam_target,
            cam_up,
            cam_fov,
            cam_near,
            cam_far,
            light_dir,
        }
    }
}
// #endregion
