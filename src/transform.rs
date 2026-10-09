// #region Transform
use glam::{Mat3, Mat4, Quat, Vec3};

pub fn compose_transform(
    translation: Option<Vec3>,
    rotation: Option<Quat>,
    scale: Option<Vec3>,
) -> Mat4 {
    let t = translation.unwrap_or(Vec3::ZERO);
    let r = rotation.unwrap_or(Quat::IDENTITY);
    let s = scale.unwrap_or(Vec3::ONE);
    Mat4::from_scale_rotation_translation(s, r, t)
}

pub fn compute_normal_matrix(model: Mat4) -> Mat4 {
    let m3 = Mat3::from_mat4(model);
    let inv_trans = m3.inverse().transpose();
    Mat4::from_mat3(inv_trans)
}
// #endregion
