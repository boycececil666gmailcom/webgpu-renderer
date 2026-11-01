// #region Imports
pub mod culling;
pub mod gltf_loader;
pub mod material;
pub mod telemetry;

pub use crate::config::Config;
pub use culling::{Frustum, FrustumPlane};
pub use gltf_loader::{
    GltfScene, GpuPrimitive, InstanceRaw, RawPrimitiveData, RenderNode, SceneCamera,
    ScatterLodConfig, SurfaceData,
};
pub use material::{Material, MaterialUniforms};
pub use telemetry::{log_error, log_info, log_warn, FrameStats, GpuInfo, LogLevel, SceneMetrics, TelemetryTracker, VramMetrics};
// #endregion

// #region Tests
#[cfg(test)]
mod tests {
    use super::*;
    use glam::{Mat4, Vec3};
    use std::time::Duration;

    #[test]
    fn test_texpresso_bc_compression() {
        let sizes = [(64, 64), (16, 16), (4, 4), (2, 2), (1, 1)];
        for (w, h) in sizes {
            let rgba = vec![255u8; w * h * 4];
            let fmt = texpresso::Format::Bc1;
            let sz = fmt.compressed_size(w, h);
            let mut out = vec![0u8; sz];
            fmt.compress(&rgba, w, h, texpresso::Params::default(), &mut out);
            assert_eq!(out.len(), sz);
            assert!(sz > 0);
        }
    }

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
        tracker.set_scene_stats(10, 25, 4000, 40, 5);
        assert_eq!(tracker.scene.mesh_count, 10);
        assert_eq!(tracker.scene.total_instances, 25);
        assert_eq!(tracker.scene.total_triangles, 4000);
        assert_eq!(tracker.scene.primitive_count, 40);
        assert_eq!(tracker.scene.material_count, 5);

        let stats = FrameStats {
            draw_calls: 15,
            triangles_drawn: 1200,
            instances_drawn: 20,
        };
        tracker.record_frame(Duration::from_millis(16), stats);
        tracker.record_frame(Duration::from_millis(8), stats);
        assert_eq!(tracker.frame_count(), 2);
    }

    #[test]
    fn test_frustum_sphere_culling() {
        let proj = Mat4::perspective_rh(std::f32::consts::FRAC_PI_2, 1.0, 0.1, 100.0);
        let view = Mat4::look_at_rh(Vec3::new(0.0, 0.0, 5.0), Vec3::ZERO, Vec3::Y);
        let frustum = Frustum::from_view_projection(proj * view);

        // Object directly in front of camera
        assert!(frustum.intersects_sphere(Vec3::new(0.0, 0.0, 0.0), 1.0));
        // Object behind the camera
        assert!(!frustum.intersects_sphere(Vec3::new(0.0, 0.0, 10.0), 1.0));
        // Object far to the right outside FOV
        assert!(!frustum.intersects_sphere(Vec3::new(50.0, 0.0, 0.0), 1.0));
        // Large object intersecting the frustum boundary
        assert!(frustum.intersects_sphere(Vec3::new(10.0, 0.0, 0.0), 12.0));
    }
}
// #endregion
