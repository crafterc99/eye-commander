"""Maps index finger tip to screen coordinates with two-stage velocity-blended EMA.

Cursor only moves in POINT mode:
  - Index finger must be up
  - Fewer than 3 non-thumb fingers up (suppresses scroll/open-palm)
  - Pinch distance above PINCH_EXIT_THRESH (cursor freezes during click/drag)

When not in point mode, the last position is held so the cursor doesn't jump.
"""

import math
import config


class HandCursor:
    def __init__(self, screen_w, screen_h):
        self._sw = screen_w
        self._sh = screen_h
        self._fast     = None   # (nx, ny) normalised
        self._slow     = None
        self._vel      = 0.0
        self._prev_out = None   # last emitted normalised position
        self._enabled  = True

    @property
    def enabled(self):
        return self._enabled

    def set_enabled(self, val):
        self._enabled = val
        if not val:
            self._reset()

    def estimate(self, hand_result):
        """Returns (screen_x, screen_y) or None."""
        if not self._enabled or hand_result is None:
            self._reset()
            return None

        from core.hand_tracker import INDEX_TIP, THUMB_TIP

        fingers  = hand_result.fingers_up()   # [thumb, index, middle, ring, pinky]
        palm_sz  = hand_result.palm_size()
        tip      = hand_result.tip(INDEX_TIP)

        # --- Pointing mode gate ---
        # 1. Index must be up
        if not fingers[1]:
            return self._hold()

        # 2. Suppress when 3+ non-thumb fingers are up (scroll, open-palm, etc.)
        if sum(fingers[1:5]) >= 3:
            return self._hold()

        # 3. Freeze during pinch (thumb+index close → click/drag in progress)
        tip_thumb = hand_result.tip(THUMB_TIP)
        pinch_d   = math.hypot(tip_thumb[0] - tip[0], tip_thumb[1] - tip[1]) / palm_sz
        if pinch_d < config.PINCH_EXIT_THRESH:
            return self._hold()

        # --- Map to normalised canvas coords, mirror X ---
        fw, fh = hand_result.frame_size
        nx = (tip[0] / fw - config.HAND_CANVAS_LEFT) / (config.HAND_CANVAS_RIGHT  - config.HAND_CANVAS_LEFT)
        ny = (tip[1] / fh - config.HAND_CANVAS_TOP)  / (config.HAND_CANVAS_BOTTOM - config.HAND_CANVAS_TOP)
        nx = max(0.0, min(1.0, 1.0 - nx))   # clamp + mirror
        ny = max(0.0, min(1.0, ny))

        # --- Two-stage velocity-blended EMA ---
        FA = config.CURSOR_FAST_ALPHA
        if self._fast is None:
            self._fast = self._slow = (nx, ny)
            self._prev_out = (nx, ny)
            return int(nx * self._sw), int(ny * self._sh)

        fx = self._fast[0] * (1 - FA) + nx * FA
        fy = self._fast[1] * (1 - FA) + ny * FA
        delta = math.hypot(fx - self._fast[0], fy - self._fast[1])
        self._vel  = self._vel * (1 - FA) + delta * FA
        self._fast = (fx, fy)

        SA = config.CURSOR_SLOW_ALPHA
        sx = self._slow[0] * (1 - SA) + fx * SA
        sy = self._slow[1] * (1 - SA) + fy * SA
        self._slow = (sx, sy)

        w  = min(config.CURSOR_VELOCITY_BLEND_MAX,
                 max(config.CURSOR_VELOCITY_BLEND_MIN,
                     self._vel * config.CURSOR_VELOCITY_BLEND_SCALE))
        ox = sx * (1 - w) + fx * w
        oy = sy * (1 - w) + fy * w

        # Dead zone
        if (self._prev_out is not None and
                math.hypot(ox - self._prev_out[0], oy - self._prev_out[1]) < config.CURSOR_DEAD_ZONE_NORM):
            return int(self._prev_out[0] * self._sw), int(self._prev_out[1] * self._sh)

        self._prev_out = (ox, oy)
        return int(ox * self._sw), int(oy * self._sh)

    # --- Helpers ---

    def _hold(self):
        """Return last known position without updating the EMA."""
        if self._prev_out is not None:
            return int(self._prev_out[0] * self._sw), int(self._prev_out[1] * self._sh)
        return None

    def _reset(self):
        self._fast = self._slow = self._prev_out = None
        self._vel  = 0.0
