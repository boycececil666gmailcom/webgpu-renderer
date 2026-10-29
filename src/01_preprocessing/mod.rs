// #region Imports
pub mod gltf_loader;
pub mod material;
pub mod telemetry;

pub use crate::config::Config;
pub use gltf_loader::{
    GltfScene, GpuPrimitive, InstanceRaw, RawPrimitiveData, RenderNode, SceneCamera, SceneLight,
    ScatterLodConfig, SurfaceData,
};
pub use material::{Material, MaterialUniforms};
pub use telemetry::{log_error, log_info, log_warn, LogLevel, SceneMetrics, TelemetryTracker};
// #endregion

// #region Tests
#[cfg(test)]
mod tests {
    use super::*;
    use glam::{Mat4, Vec3};
    use std::time::Duration;

    #[test]
    fn test_instance_raw_identity() {
        let raw = InstanceRaw::from_transform(Mat4::IDENTITY);
        assert_eq!(raw.model[0][0], 1.0);
        assert_eq!(raw.model[1][1], 1.0);
        assert_eq!(raw.model[2][2], 1.0);
        assert_eq!(raw.model[3][3], 1.0);
        assert_eq!(raw.normal_matrix[0][0], 1.0);
        assert_eq!(raw.normal_matrix[3][3], 1.0);
    }

    #[test]
    fn test_scene_camera_projection() {
        let camera = SceneCamera {
            name: Some("MainCamera".to_string()),
            world_transform: Mat4::IDENTITY,
            yfov: 1.0,
            znear: 0.1,
            zfar: None,
        };
        let proj = camera.projection_matrix(16.0 / 9.0);
        assert!(proj.x_axis.x > 0.0);
        assert!(proj.y_axis.y > 0.0);
        assert_eq!(camera.position(), Vec3::ZERO);
        assert_eq!(camera.view_matrix(), Mat4::IDENTITY);
    }

    #[test]
    fn test_telemetry_metrics_accumulation() {
        let mut tracker = TelemetryTracker::new();
        tracker.set_resolution(1920, 1080);
        assert_eq!(tracker.resolution(), (1920, 1080));
        tracker.set_scene_stats(10, 25, 40, 5);
        assert_eq!(tracker.scene.mesh_count, 10);
        assert_eq!(tracker.scene.instance_count, 25);
        assert_eq!(tracker.scene.primitive_count, 40);
        assert_eq!(tracker.scene.material_count, 5);

        tracker.record_frame(Duration::from_millis(16));
        tracker.record_frame(Duration::from_millis(8));
        assert_eq!(tracker.frame_count(), 2);
    }
}
// #endregion
