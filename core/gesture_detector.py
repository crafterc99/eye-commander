"""Gesture state machines with hysteresis — pinch, fist, peace, scroll, open palm."""

import time
import config
from core.hand_tracker import (
    THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP,
    INDEX_MCP, MIDDLE_MCP
)


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

        # --- Pinch state machine ---
        # States: IDLE | CHARGING | DRAGGING
        self._pinch_state      = "IDLE"
        self._pinch_start_time = 0.0
        self._last_click_time  = 0.0

        # --- Fist state machine ---
        # States: IDLE | CHARGING | PAUSED
        self._fist_state       = "IDLE"
        self._fist_start_time  = 0.0
        self._fist_charge_ratio = 0.0
        self._open_frame_count  = 0   # consecutive open-hand frames while PAUSED

        # --- Peace state machine ---
        # States: IDLE | CONFIRMING | COOLDOWN
        self._peace_state       = "IDLE"
        self._peace_frame_count = 0
        self._peace_cooldown_until = 0.0

        # --- Continuous scroll ---
        self._scroll_prev_y    = None
        self._scroll_vel       = 0.0
        self._scroll_accum     = 0.0

        self._last_gesture = ""

    # --- Public ---

    @property
    def last_gesture(self):
        return self._last_gesture

    def is_dragging(self):
        return self._pinch_state == "DRAGGING"

    def get_hud_state(self):
        return {"fist_charge": self._fist_charge_ratio}

    def update(self, hand_result):
        """Call every frame. Returns current gesture label."""
        if hand_result is None:
            self._handle_no_hand()
            return "no hand"

        ps   = hand_result.palm_size()
        fingers = hand_result.fingers_up()   # [thumb, index, middle, ring, pinky]
        tip_thumb  = hand_result.tip(THUMB_TIP)
        tip_index  = hand_result.tip(INDEX_TIP)
        tip_middle = hand_result.tip(MIDDLE_TIP)

        pinch_dist = _dist(tip_thumb, tip_index) / ps
        now = time.time()

        # Priority order: fist > pinch > peace > scroll

        is_fist   = not any(fingers)
        three_up  = fingers[1] and fingers[2] and fingers[3] and not fingers[4]
        peace_raw = fingers[1] and fingers[2] and not fingers[3] and not fingers[4]
        all_4_up  = fingers[1] and fingers[2] and fingers[3] and fingers[4]

        # --- Fist state machine ---
        if self._fist_state == "PAUSED":
            if all_4_up:
                self._open_frame_count += 1
                if self._open_frame_count >= config.FIST_EXIT_OPEN_FRAMES:
                    self._fist_state = "IDLE"
                    self._fist_charge_ratio = 0.0
                    self._open_frame_count = 0
                    self._on_resume()
                    self._last_gesture = "open → resume"
            else:
                self._open_frame_count = 0
            # While paused, skip other gesture checks
            return self._last_gesture

        if is_fist:
            if self._fist_state == "IDLE":
                self._fist_state = "CHARGING"
                self._fist_start_time = now
                self._fist_charge_ratio = 0.0
            elif self._fist_state == "CHARGING":
                elapsed = now - self._fist_start_time
                self._fist_charge_ratio = min(1.0, elapsed / config.FIST_ENTER_HOLD_SECS)
                if elapsed >= config.FIST_ENTER_HOLD_SECS:
                    self._fist_state = "PAUSED"
                    self._open_frame_count = 0
                    self._on_pause()
                    self._last_gesture = "fist → pause"
                    return self._last_gesture
        else:
            if self._fist_state == "CHARGING":
                # Canceled — hand opened before hold completed
                self._fist_state = "IDLE"
                self._fist_charge_ratio = 0.0

        # --- Pinch state machine ---
        if self._pinch_state == "IDLE":
            if pinch_dist < config.PINCH_ENTER_THRESH:
                self._pinch_state = "CHARGING"
                self._pinch_start_time = now

        elif self._pinch_state == "CHARGING":
            if pinch_dist > config.PINCH_EXIT_THRESH:
                # Released before drag threshold — fire click if fast enough
                held = now - self._pinch_start_time
                if held < config.DRAG_HOLD_SECS:
                    if now - self._last_click_time > config.PINCH_COOLDOWN_SECS:
                        self._last_click_time = now
                        self._on_click()
                        self._last_gesture = "pinch → click"
                self._pinch_state = "IDLE"
            elif now - self._pinch_start_time >= config.DRAG_HOLD_SECS:
                self._pinch_state = "DRAGGING"
                self._on_drag_start()
                self._last_gesture = "pinch hold → drag"

        elif self._pinch_state == "DRAGGING":
            if pinch_dist > config.PINCH_EXIT_THRESH:
                self._pinch_state = "IDLE"
                self._on_drag_end()
                self._last_gesture = "drag end"

        # --- Peace state machine (right click) ---
        peace_spread = _dist(tip_index, tip_middle) / ps if peace_raw else 0.0
        peace_valid  = peace_raw and peace_spread > config.PEACE_SPREAD_THRESH

        if self._peace_state == "IDLE":
            if peace_valid and now >= self._peace_cooldown_until:
                self._peace_state = "CONFIRMING"
                self._peace_frame_count = 1

        elif self._peace_state == "CONFIRMING":
            if not peace_valid:
                self._peace_state = "IDLE"
                self._peace_frame_count = 0
            else:
                self._peace_frame_count += 1
                if self._peace_frame_count >= config.PEACE_HOLD_FRAMES:
                    self._on_right_click()
                    self._last_gesture = "peace → right click"
                    self._peace_state = "IDLE"
                    self._peace_frame_count = 0
                    self._peace_cooldown_until = now + config.PINCH_COOLDOWN_SECS

        # --- Continuous scroll (3 fingers up) ---
        if three_up:
            fw, fh = hand_result.frame_size
            cy = hand_result.palm_center()[1] / fh
            if self._scroll_prev_y is None:
                self._scroll_prev_y = cy
            else:
                raw_delta = self._scroll_prev_y - cy   # positive = hand moved up = scroll up
                self._scroll_prev_y = cy
                self._scroll_vel = (self._scroll_vel * (1 - config.SCROLL_SMOOTHING)
                                    + raw_delta * config.SCROLL_SMOOTHING)
                if abs(self._scroll_vel) > config.SCROLL_MIN_VELOCITY:
                    self._scroll_accum += self._scroll_vel * config.SCROLL_VELOCITY_SCALE
                    whole = int(self._scroll_accum)
                    if whole != 0:
                        self._on_scroll(0, whole)
                        self._scroll_accum -= whole
                        self._last_gesture = f"scroll {'up' if whole > 0 else 'down'}"
        else:
            self._scroll_prev_y = None
            self._scroll_vel    = 0.0
            self._scroll_accum  = 0.0

        return self._last_gesture

    # --- Internal ---

    def _handle_no_hand(self):
        if self._pinch_state == "DRAGGING":
            self._on_drag_end()
        self._pinch_state = "IDLE"
        self._scroll_prev_y = None
        self._scroll_vel    = 0.0
        self._scroll_accum  = 0.0
        # Don't cancel fist PAUSED — hand may briefly disappear
        if self._fist_state == "CHARGING":
            self._fist_state = "IDLE"
            self._fist_charge_ratio = 0.0


def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
