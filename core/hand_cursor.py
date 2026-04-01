"""Maps index finger tip position to screen coordinates with EMA smoothing."""

import config

# The "virtual canvas" within the camera frame that maps to the full screen.
# Shrinking it makes edge-of-screen easier to reach.
CANVAS_LEFT   = 0.15
CANVAS_RIGHT  = 0.85
CANVAS_TOP    = 0.10
CANVAS_BOTTOM = 0.85


class HandCursor:
    def __init__(self, screen_w, screen_h):
        self._sw = screen_w
        self._sh = screen_h
        self._prev = None
        self._enabled = True

    @property
    def enabled(self):
        return self._enabled

    def set_enabled(self, val):
        self._enabled = val

    def estimate(self, hand_result):
        """Returns (screen_x, screen_y) from index finger tip, or None."""
        if not self._enabled or hand_result is None:
            return None

        from core.hand_tracker import INDEX_TIP
        tip = hand_result.tip(INDEX_TIP)
        fw, fh = hand_result.frame_size

        # Normalise to [0,1]
        nx = tip[0] / fw
        ny = tip[1] / fh

        # Map virtual canvas → screen
        nx_mapped = (nx - CANVAS_LEFT) / (CANVAS_RIGHT - CANVAS_LEFT)
        ny_mapped = (ny - CANVAS_TOP)  / (CANVAS_BOTTOM - CANVAS_TOP)
        nx_mapped = max(0.0, min(1.0, nx_mapped))
        ny_mapped = max(0.0, min(1.0, ny_mapped))

        # Mirror X (camera is flipped)
        nx_mapped = 1.0 - nx_mapped

        sx = nx_mapped * self._sw
        sy = ny_mapped * self._sh

        return self._smooth(sx, sy)

    def _smooth(self, x, y):
        alpha = config.GAZE_EMA_ALPHA
        if self._prev is None:
            self._prev = (x, y)
            return x, y
        px, py = self._prev
        sx = px * (1 - alpha) + x * alpha
        sy = py * (1 - alpha) + y * alpha
        if abs(sx - px) < config.GAZE_DEAD_ZONE_PX and abs(sy - py) < config.GAZE_DEAD_ZONE_PX:
            return px, py
        self._prev = (sx, sy)
        return sx, sy
