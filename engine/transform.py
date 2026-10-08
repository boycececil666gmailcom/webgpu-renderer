# region Transform
import numpy as np


def look_at(eye, target, up) -> np.ndarray:
    """Calculates a 4x4 right-handed view matrix."""
    eye = np.asarray(eye, dtype=np.float32)
    target = np.asarray(target, dtype=np.float32)
    up = np.asarray(up, dtype=np.float32)

    f = target - eye
    f /= np.linalg.norm(f)
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)

    m = np.eye(4, dtype=np.float32)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = -np.dot(s, eye)
    m[1, 3] = -np.dot(u, eye)
    m[2, 3] = np.dot(f, eye)
    return m


def perspective(fovy_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    """Calculates a 4x4 WebGPU perspective projection matrix (Z depth range: [0, 1])."""
    fovy_rad = np.radians(fovy_deg)
    tan_half = np.tan(fovy_rad / 2.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = 1.0 / (aspect * tan_half)
    m[1, 1] = 1.0 / tan_half
    m[2, 2] = far / (near - far)
    m[2, 3] = -(far * near) / (far - near)
    m[3, 2] = -1.0
    return m


def quat_to_mat4(q) -> np.ndarray:
    """Converts a quaternion [x, y, z, w] to a 4x4 rotation matrix."""
    x, y, z, w = float(q[0]), float(q[1]), float(q[2]), float(q[3])
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = 1.0 - 2.0 * (y * y + z * z)
    m[0, 1] = 2.0 * (x * y - z * w)
    m[0, 2] = 2.0 * (x * z + y * w)
    m[1, 0] = 2.0 * (x * y + z * w)
    m[1, 1] = 1.0 - 2.0 * (x * x + z * z)
    m[1, 2] = 2.0 * (y * z - x * w)
    m[2, 0] = 2.0 * (x * z - y * w)
    m[2, 1] = 2.0 * (y * z + x * w)
    m[2, 2] = 1.0 - 2.0 * (x * x + y * y)
    return m


def compose_transform(translation=None, rotation=None, scale=None) -> np.ndarray:
    """Composes translation, rotation quaternion [x,y,z,w], and scale into a 4x4 matrix."""
    m = np.eye(4, dtype=np.float32)
    if translation is not None:
        t = np.eye(4, dtype=np.float32)
        t[:3, 3] = translation
        m = m @ t
    if rotation is not None:
        m = m @ quat_to_mat4(rotation)
    if scale is not None:
        s = np.eye(4, dtype=np.float32)
        s[0, 0] = scale[0]
        s[1, 1] = scale[1]
        s[2, 2] = scale[2]
        m = m @ s
    return m


def normal_matrix(model_matrix: np.ndarray) -> np.ndarray:
    """Computes the 4x4 normal transformation matrix (inverse transpose of upper 3x3)."""
    norm = np.eye(4, dtype=np.float32)
    norm[:3, :3] = np.linalg.inv(model_matrix[:3, :3]).T
    return norm
# endregion
