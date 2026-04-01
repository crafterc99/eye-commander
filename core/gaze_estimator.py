"""Iris position → screen coordinates with EMA smoothing and calibration."""

import numpy as np
import config


class GazeEstimator:
    def __init__(self):
        self._calibration = None   # set by calibration module
        self._prev_screen = None
        self._enabled = True

    def set_calibration(self, calibration_data):
        """
        calibration_data: list of (iris_norm, screen_pos) tuples
        iris_norm: (gx, gy) normalised iris in [0,1] within eye bbox
        screen_pos: (sx, sy) pixel position on screen
        """
        self._calibration = calibration_data

    @property
    def enabled(self):
        return self._enabled

    def set_enabled(self, val: bool):
        self._enabled = val

    def estimate(self, face_result):
        """
        Returns (screen_x, screen_y) or None if tracking disabled / no calibration.
        Uses average of both irises, then maps through calibration grid.
        """
        if not self._enabled or self._calibration is None:
            return None

        # Average both iris positions for robustness
        rx, ry = face_result.iris_right
        lx, ly = face_result.iris_left
        raw_x = (rx + lx) / 2.0
        raw_y = (ry + ly) / 2.0
        fw, fh = face_result.frame_size

        # Normalise to [0,1] within frame
        norm_x = raw_x / fw
        norm_y = raw_y / fh

        screen_x, screen_y = self._interpolate(norm_x, norm_y)
        screen_x, screen_y = self._smooth(screen_x, screen_y)
        return screen_x, screen_y

    def _interpolate(self, nx, ny):
        """Bilinear interpolation from 9-point calibration grid."""
        cal = self._calibration  # list of (iris_norm, screen_pos)

        if len(cal) == 0:
            return 0, 0

        # Find 4 nearest calibration points
        dists = [((nx - c[0][0])**2 + (ny - c[0][1])**2, c) for c in cal]
        dists.sort(key=lambda d: d[0])
        nearest = dists[:4]

        total_w = 0.0
        sx, sy = 0.0, 0.0
        for dist_sq, (iris_norm, screen_pos) in nearest:
            w = 1.0 / (dist_sq + 1e-6)
            sx += screen_pos[0] * w
            sy += screen_pos[1] * w
            total_w += w
        return sx / total_w, sy / total_w

    def _smooth(self, x, y):
        alpha = config.GAZE_EMA_ALPHA
        if self._prev_screen is None:
            self._prev_screen = (x, y)
            return x, y
        px, py = self._prev_screen
        sx = px * (1 - alpha) + x * alpha
        sy = py * (1 - alpha) + y * alpha
        # Dead zone
        if abs(sx - px) < config.GAZE_DEAD_ZONE_PX and abs(sy - py) < config.GAZE_DEAD_ZONE_PX:
            return px, py
        self._prev_screen = (sx, sy)
        return sx, sy
