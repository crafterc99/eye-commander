"""Eye Aspect Ratio blink detector — fires left/right/both blink events."""

import time
import numpy as np
import config


def _ear(pts):
    """Compute Eye Aspect Ratio from 6 landmark points."""
    p1, p2, p3, p4, p5, p6 = [np.array(p) for p in pts]
    a = np.linalg.norm(p2 - p6)
    b = np.linalg.norm(p3 - p5)
    c = np.linalg.norm(p1 - p4)
    return (a + b) / (2.0 * c) if c > 0 else 1.0


class BlinkDetector:
    def __init__(self, callback):
        """
        callback(event): event is 'left', 'right', or 'both'
        """
        self._callback = callback
        self._left_closed_start = None
        self._right_closed_start = None
        self._last_click_time = 0.0
        self._left_was_closed = False
        self._right_was_closed = False

    def update(self, face_result):
        ear_r = _ear(face_result.ear_right_pts)
        ear_l = _ear(face_result.ear_left_pts)

        now = time.time()
        r_closed = ear_r < config.EAR_THRESHOLD
        l_closed = ear_l < config.EAR_THRESHOLD

        # Track close start times
        if r_closed and not self._right_was_closed:
            self._right_closed_start = now
        if l_closed and not self._left_was_closed:
            self._left_closed_start = now

        # Detect blink on eye open (transition closed → open)
        r_blink = self._right_was_closed and not r_closed
        l_blink = self._left_was_closed and not l_closed

        if r_blink or l_blink:
            # Check cooldown
            if now - self._last_click_time >= config.BLINK_COOLDOWN_MS / 1000.0:
                if r_blink and l_blink:
                    self._callback("both")
                elif l_blink:
                    self._callback("left")
                elif r_blink:
                    self._callback("right")
                self._last_click_time = now

        self._right_was_closed = r_closed
        self._left_was_closed = l_closed

        return ear_r, ear_l
