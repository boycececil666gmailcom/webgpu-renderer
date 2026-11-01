// #region Imports
pub mod renderer;

pub use renderer::{FrameUniforms, Renderer};
// #endregion

// #region Tests
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_frame_uniforms_layout() {
        let uniforms = FrameUniforms {
            view: [[0.0; 4]; 4],
            projection: [[0.0; 4]; 4],
            cam_pos: [0.0; 4],
        };
        let bytes = bytemuck::bytes_of(&uniforms);
        // 16 floats (view) + 16 floats (proj) + 4 (cam_pos) = 36 floats = 144 bytes
        assert_eq!(bytes.len(), 144);
    }
}
// #endregion
