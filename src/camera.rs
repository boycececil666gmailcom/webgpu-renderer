// #region Camera
use glam::{Mat4, Vec3};

#[derive(Debug, Clone)]
pub struct Camera {
    pub pos: Vec3,
    pub target: Vec3,
    pub up: Vec3,
    pub fov: f32,
    pub near: f32,
    pub far: f32,
}

impl Camera {
    pub fn new(pos: Vec3, target: Vec3, up: Vec3, fov: f32, near: f32, far: f32) -> Self {
        Self {
            pos,
            target,
            up,
            fov,
            near,
            far,
        }
    }

    pub fn get_view_matrix(&self) -> Mat4 {
        Mat4::look_at_rh(self.pos, self.target, self.up)
    }

    pub fn get_projection_matrix(&self, aspect_ratio: f32) -> Mat4 {
        Mat4::perspective_rh(self.fov.to_radians(), aspect_ratio, self.near, self.far)
    }
}
// #endregion
