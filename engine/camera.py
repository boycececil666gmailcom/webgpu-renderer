# region Imports
import numpy as np

from engine.transform import look_at, perspective

# endregion


# region Camera Class
class Camera:
    """Encapsulates 3D camera properties and transformation matrices for WebGPU."""

    def __init__(
        self,
        pos=None,
        target=None,
        up=None,
        fov: float = 45.0,
        near: float = 0.1,
        far: float = 100.0,
    ):
        self.pos = (
            np.array([0.0, 0.5, 3.5], dtype=np.float32)
            if pos is None
            else np.asarray(pos, dtype=np.float32)
        )
        self.target = (
            np.array([0.0, 0.0, 0.0], dtype=np.float32)
            if target is None
            else np.asarray(target, dtype=np.float32)
        )
        self.up = (
            np.array([0.0, 1.0, 0.0], dtype=np.float32)
            if up is None
            else np.asarray(up, dtype=np.float32)
        )
        self.fov = float(fov)
        self.near = float(near)
        self.far = float(far)

    def get_view_matrix(self) -> np.ndarray:
        """Returns the 4x4 View transformation matrix."""
        return look_at(self.pos, self.target, self.up)

    def get_projection_matrix(self, aspect_ratio: float) -> np.ndarray:
        """Returns the 4x4 Perspective Projection matrix for WebGPU [0, 1] clip depth."""
        return perspective(self.fov, aspect_ratio, self.near, self.far)


# endregion
