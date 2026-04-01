"""Gesture state machine — detects pinch, fist, peace, swipe, open palm."""

import time
import numpy as np
from core.hand_tracker import (
    THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP,
    INDEX_MCP, MIDDLE_MCP
)

# Thresholds (relative to palm_size)
PINCH_THRESH   = 0.35   # thumb+index tip distance / palm_size
CLICK_COOLDOWN = 0.45   # seconds between clicks
DRAG_HOLD_SECS = 0.4    # hold pinch this long to start drag
SWIPE_MIN_DIST = 0.15   # normalised frame units for swipe detection
SWIPE_WINDOW   = 0.5    # seconds to complete a swipe


class GestureDetector:
    def __init__(self, on_click, on_right_click, on_double_click,
                 on_scroll, on_drag_start, on_drag_end, on_pause, on_resume):
        self._on_click        = on_click
        self._on_right_click  = on_right_click
        self._on_double_click = on_double_click
        self._on_scroll       = on_scroll
        self._on_drag_start   = on_drag_start
        self._on_drag_end     = on_drag_end
        self._on_pause        = on_pause
        self._on_resume       = on_resume

        self._last_click_time  = 0.0
        self._pinch_start_time = None
        self._dragging         = False
        self._prev_fingers_up  = None
        self._fist_start_time  = None
        self._paused_by_fist   = False

        # Swipe tracking
        self._swipe_start_y    = None
        self._swipe_start_time = None

        self._last_gesture     = ""

    @property
    def last_gesture(self):
        return self._last_gesture

    def update(self, hand_result):
        """Call every frame. Returns current gesture label string."""
        if hand_result is None:
            self._reset_pinch()
            return "no hand"

        ps = hand_result.palm_size()
        fingers = hand_result.fingers_up()  # [thumb, index, middle, ring, pinky]
        tip_thumb = hand_result.tip(THUMB_TIP)
        tip_index = hand_result.tip(INDEX_TIP)
        tip_middle= hand_result.tip(MIDDLE_TIP)

        pinch_dist = _dist(tip_thumb, tip_index) / ps

        now = time.time()

        # --- Fist = pause/resume ---
        is_fist = not any(fingers)
        if is_fist:
            if self._fist_start_time is None:
                self._fist_start_time = now
            elif now - self._fist_start_time > 0.8 and not self._paused_by_fist:
                self._paused_by_fist = True
                self._on_pause()
                self._last_gesture = "fist → pause"
        else:
            if self._paused_by_fist and self._fist_start_time is not None:
                # open hand after fist = resume
                if all(fingers[1:4]):  # index+middle+ring = open
                    self._paused_by_fist = False
                    self._on_resume()
                    self._last_gesture = "open → resume"
            self._fist_start_time = None

        # --- Pinch = click / drag ---
        if pinch_dist < PINCH_THRESH:
            if self._pinch_start_time is None:
                self._pinch_start_time = now
            elif not self._dragging and now - self._pinch_start_time > DRAG_HOLD_SECS:
                self._dragging = True
                self._on_drag_start()
                self._last_gesture = "pinch hold → drag"
        else:
            if self._pinch_start_time is not None:
                held = now - self._pinch_start_time
                if self._dragging:
                    self._dragging = False
                    self._on_drag_end()
                    self._last_gesture = "drag end"
                elif held < DRAG_HOLD_SECS:
                    # Quick pinch = click
                    if now - self._last_click_time > CLICK_COOLDOWN:
                        self._last_click_time = now
                        self._on_click()
                        self._last_gesture = "pinch → click"
                self._pinch_start_time = None

        # --- Peace sign = right click ---
        peace = fingers[1] and fingers[2] and not fingers[3] and not fingers[4]
        peace_pinch = _dist(tip_index, tip_middle) / ps
        if peace and peace_pinch < PINCH_THRESH * 1.2:
            if now - self._last_click_time > CLICK_COOLDOWN:
                self._last_click_time = now
                self._on_right_click()
                self._last_gesture = "peace pinch → right click"

        # --- Three fingers up = scroll mode: track Y movement ---
        three_up = fingers[1] and fingers[2] and fingers[3] and not fingers[4]
        if three_up:
            fw, fh = hand_result.frame_size
            cy = hand_result.palm_center()[1] / fh
            if self._swipe_start_y is None:
                self._swipe_start_y = cy
                self._swipe_start_time = now
            else:
                delta = self._swipe_start_y - cy  # positive = moved up
                elapsed = now - self._swipe_start_time
                if abs(delta) > SWIPE_MIN_DIST and elapsed < SWIPE_WINDOW:
                    ticks = max(1, int(abs(delta) * 20))
                    self._on_scroll(0, ticks if delta > 0 else -ticks)
                    self._last_gesture = f"scroll {'up' if delta>0 else 'down'}"
                    self._swipe_start_y = cy
                    self._swipe_start_time = now
        else:
            self._swipe_start_y = None

        return self._last_gesture

    def is_dragging(self):
        return self._dragging

    def _reset_pinch(self):
        if self._dragging:
            self._on_drag_end()
            self._dragging = False
        self._pinch_start_time = None


def _dist(a, b):
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5
