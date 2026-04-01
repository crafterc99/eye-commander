"""Maps index finger tip position to screen coordinates.

Two-stage velocity-blended cursor:
  fast EMA  → tracks intent
  slow EMA  → kills residual jitter
  velocity  → blends toward fast EMA when moving, toward slow when still
"""

import math
import config


class HandCursor:
    def __init__(self, screen_w, screen_h):
        self._sw = screen_w
        self._sh = screen_h
        self._fast = None   # (nx, ny) normalised
        self._slow = None   # (nx, ny) normalised
        self._vel  = 0.0    # smoothed velocity magnitude
        self._prev_out = None  # for dead-zone check
        self._enabled = True

    @property
    def enabled(self):
        return self._enabled

    def set_enabled(self, val):
        self._enabled = val

    def estimate(self, hand_result):
        """Returns (screen_x, screen_y) from index finger tip, or None."""
        if not self._enabled or hand_result is None:
            self._fast = self._slow = self._prev_out = None
            self._vel = 0.0
            return None

        from core.hand_tracker import INDEX_TIP
        tip = hand_result.tip(INDEX_TIP)
        fw, fh = hand_result.frame_size

        # 1. Normalise to canvas then mirror X
        nx = (tip[0] / fw - config.HAND_CANVAS_LEFT) / (config.HAND_CANVAS_RIGHT  - config.HAND_CANVAS_LEFT)
        ny = (tip[1] / fh - config.HAND_CANVAS_TOP)  / (config.HAND_CANVAS_BOTTOM - config.HAND_CANVAS_TOP)
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))
        nx = 1.0 - nx  # mirror

        # 2. Fast EMA
        FA = config.CURSOR_FAST_ALPHA
        if self._fast is None:
            self._fast = (nx, ny)
            self._slow = (nx, ny)
            self._prev_out = (nx, ny)
            return int(nx * self._sw), int(ny * self._sh)

        fx = self._fast[0] * (1 - FA) + nx * FA
        fy = self._fast[1] * (1 - FA) + ny * FA

        # 3. Velocity (delta of fast EMA, smoothed)
        delta = math.hypot(fx - self._fast[0], fy - self._fast[1])
        self._vel = self._vel * (1 - config.CURSOR_FAST_ALPHA) + delta * config.CURSOR_FAST_ALPHA
        self._fast = (fx, fy)

        # 4. Slow EMA
        SA = config.CURSOR_SLOW_ALPHA
        sx = self._slow[0] * (1 - SA) + fx * SA
        sy = self._slow[1] * (1 - SA) + fy * SA
        self._slow = (sx, sy)

        # 5. Velocity blend weight
        w = self._vel * config.CURSOR_VELOCITY_BLEND_SCALE
        w = max(config.CURSOR_VELOCITY_BLEND_MIN, min(config.CURSOR_VELOCITY_BLEND_MAX, w))

        # 6. Output
        ox = sx * (1 - w) + fx * w
        oy = sy * (1 - w) + fy * w

        # 7. Dead zone in normalised units
        if self._prev_out is not None:
            if math.hypot(ox - self._prev_out[0], oy - self._prev_out[1]) < config.CURSOR_DEAD_ZONE_NORM:
                return int(self._prev_out[0] * self._sw), int(self._prev_out[1] * self._sh)

        self._prev_out = (ox, oy)
        return int(ox * self._sw), int(oy * self._sh)
