// #region Imports
use glam::{Mat4, Vec3, Vec4};
// #endregion

// #region Types
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct FrustumPlane {
    pub normal: Vec3,
    pub distance: f32,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Frustum {
    pub planes: [FrustumPlane; 6],
}
// #endregion

// #region Scaffolding
impl FrustumPlane {
    #[inline]
    pub fn new(raw: Vec4) -> Self {
        let normal = Vec3::new(raw.x, raw.y, raw.z);
        let len = normal.length();
        if len > 1e-6 {
            Self {
                normal: normal / len,
                distance: raw.w / len,
            }
        } else {
            Self {
                normal: Vec3::ZERO,
                distance: 0.0,
            }
        }
    }

    #[inline(always)]
    pub fn signed_distance(&self, point: Vec3) -> f32 {
        self.normal.dot(point) + self.distance
    }
}
// #endregion

// #region Domain
impl Frustum {
    /// Extracts the 6 frustum planes from a combined view-projection matrix.
    /// WebGPU uses clip space with depth range [0, 1]:
    /// -w <= x <= w, -w <= y <= w, 0 <= z <= w.
    pub fn from_view_projection(vp: Mat4) -> Self {
        let r0 = vp.row(0);
        let r1 = vp.row(1);
        let r2 = vp.row(2);
        let r3 = vp.row(3);

        Self {
            planes: [
                FrustumPlane::new(r3 + r0), // Left:   w + x >= 0
                FrustumPlane::new(r3 - r0), // Right:  w - x >= 0
                FrustumPlane::new(r3 + r1), // Bottom: w + y >= 0
                FrustumPlane::new(r3 - r1), // Top:    w - y >= 0
                FrustumPlane::new(r2),      // Near:   z >= 0 (WebGPU [0, 1] range)
                FrustumPlane::new(r3 - r2), // Far:    w - z >= 0
            ],
        }
    }

    /// Evaluates whether a bounding sphere intersects or is inside the frustum.
    /// Returns false if the sphere is completely behind any single plane.
    #[inline(always)]
    pub fn intersects_sphere(&self, center: Vec3, radius: f32) -> bool {
        for plane in &self.planes {
            if plane.signed_distance(center) < -radius {
                return false;
            }
        }
        true
    }

    /// Evaluates whether an Axis-Aligned Bounding Box (AABB) intersects or is inside the frustum.
    #[inline(always)]
    pub fn intersects_aabb(&self, min: Vec3, max: Vec3) -> bool {
        for plane in &self.planes {
            let px = if plane.normal.x >= 0.0 { max.x } else { min.x };
            let py = if plane.normal.y >= 0.0 { max.y } else { min.y };
            let pz = if plane.normal.z >= 0.0 { max.z } else { min.z };
            if plane.signed_distance(Vec3::new(px, py, pz)) < 0.0 {
                return false;
            }
        }
        true
    }
}
// #endregion

