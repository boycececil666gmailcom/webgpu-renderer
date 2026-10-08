# region Imports
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

# endregion


# region Configuration Class
class Config:
    def __init__(self):
        # Load environment variables from project root .env
        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(dotenv_path=env_path)

        # Window & Graphics API settings
        self.scr_width = int(os.environ.get("SCR_WIDTH", 1280))
        self.scr_height = int(os.environ.get("SCR_HEIGHT", 720))
        self.target_fps = int(os.environ.get("TARGET_FPS", 165))
        self.target_frame_time = 1.0 / self.target_fps if self.target_fps > 0 else 0.0

        # Camera configuration (pure NumPy float32)
        self.cam_pos = np.array(
            [
                float(os.environ.get("CAM_POS_X", 0.0)),
                float(os.environ.get("CAM_POS_Y", 0.5)),
                float(os.environ.get("CAM_POS_Z", 3.5)),
            ],
            dtype=np.float32,
        )
        self.cam_target = np.array(
            [
                float(os.environ.get("CAM_TARGET_X", 0.0)),
                float(os.environ.get("CAM_TARGET_Y", 0.0)),
                float(os.environ.get("CAM_TARGET_Z", 0.0)),
            ],
            dtype=np.float32,
        )
        self.cam_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        self.cam_fov = float(os.environ.get("CAM_FOV", 45.0))
        self.cam_near = float(os.environ.get("CAM_NEAR", 0.1))
        self.cam_far = float(os.environ.get("CAM_FAR", 100.0))

        # Directional Light configuration (pure NumPy float32)
        self.light_dir = np.array(
            [
                float(os.environ.get("LIGHT_DIR_X", 0.3)),
                float(os.environ.get("LIGHT_DIR_Y", 1.0)),
                float(os.environ.get("LIGHT_DIR_Z", 0.5)),
            ],
            dtype=np.float32,
        )


# endregion
