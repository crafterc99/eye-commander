"""Eye gaze → screen coordinates using GazeTracking (dlib-based).

Runs GazeTracking in a background thread so it never blocks the main loop.
Maps horizontal/vertical iris ratios to screen with auto-calibration and
two-stage EMA smoothing.

  horizontal_ratio: 0.0 = looking right, 1.0 = looking left  (flip!)
  vertical_ratio:   0.0 = looking up,    1.0 = looking down
"""

import queue
import threading
import time

_FAST_A = 0.20    # first EMA — tracks motion
_SLOW_A = 0.08    # second EMA — kills tremor
_VEL_SCALE = 60.0
_VEL_MAX   = 0.90
_CALIB_FRAMES = 45   # ~1.5s to establish neutral gaze


class GazeCursor:
    def __init__(self, screen_w: int, screen_h: int):
        from gaze_tracking import GazeTracking
        self._gaze    = GazeTracking()
        self._sw      = screen_w
        self._sh      = screen_h
        self._latest  = None          # (sx, sy) float
        self._lock    = threading.Lock()
        self._q       = queue.Queue(maxsize=1)
        self._enabled = True

        # Auto-calibration state
        self._calib_h: list = []
        self._calib_v: list = []
        self._calibrated = False
        self._center_h   = 0.50
        self._center_v   = 0.50
        self._gain_h     = 2.5    # how much 1 unit of ratio → screen fraction
        self._gain_v     = 2.5

        # Two-stage smoothing
        self._fast = None
        self._slow = None
        self._vel  = 0.0

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    @property
    def enabled(self):
        return self._enabled

    def set_enabled(self, val: bool):
        self._enabled = val

    @property
    def calibrated(self):
        return self._calibrated

    def recalibrate(self):
        """Reset calibration — look straight ahead for ~1.5s to recalibrate."""
        self._calib_h = []
        self._calib_v = []
        self._calibrated = False
        self._fast = self._slow = None
        print("[gaze] Recalibrating — look straight ahead...")

    def submit_frame(self, frame_bgr):
        """Non-blocking — drop frame if thread still busy."""
        if not self._enabled:
            return
        try:
            self._q.put_nowait(frame_bgr.copy())
        except queue.Full:
            pass

    def latest_pos(self):
        """Returns (sx, sy) in screen pixels or None."""
        with self._lock:
            return self._latest

    # --- Background thread ---

    def _loop(self):
        while True:
            frame = self._q.get()
            self._gaze.refresh(frame)

            if not self._gaze.pupils_located:
                with self._lock:
                    self._latest = None
                continue

            h = self._gaze.horizontal_ratio()
            v = self._gaze.vertical_ratio()
            if h is None or v is None:
                with self._lock:
                    self._latest = None
                continue

            pos = self._map(h, v)
            with self._lock:
                self._latest = pos

    def _map(self, h: float, v: float):
        # --- Auto-calibration ---
        if not self._calibrated:
            self._calib_h.append(h)
            self._calib_v.append(v)
            if len(self._calib_h) >= _CALIB_FRAMES:
                self._center_h = sum(self._calib_h) / len(self._calib_h)
                self._center_v = sum(self._calib_v) / len(self._calib_v)
                # Estimate range → derive gain
                h_range = max(self._calib_h) - min(self._calib_h) + 0.05
                v_range = max(self._calib_v) - min(self._calib_v) + 0.05
                self._gain_h = 0.7 / h_range   # 0.7 of screen per full eye range
                self._gain_v = 0.7 / v_range
                self._calibrated = True
                print(f"[gaze] Calibrated: center=({self._center_h:.3f},{self._center_v:.3f})")
            return None   # don't emit position during calibration

        # GazeTracking h_ratio: 0=right, 1=left → flip so 0=left
        dx = -(h - self._center_h)   # flip + center
        dy =  (v - self._center_v)

        nx = 0.5 + dx * self._gain_h
        ny = 0.5 + dy * self._gain_v
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))

        return self._smooth(nx * self._sw, ny * self._sh)

    def _smooth(self, x: float, y: float):
        import math
        if self._fast is None:
            self._fast = self._slow = (x, y)
            return x, y

        fx = self._fast[0] * (1 - _FAST_A) + x * _FAST_A
        fy = self._fast[1] * (1 - _FAST_A) + y * _FAST_A
        delta = math.hypot(fx - self._fast[0], fy - self._fast[1])
        self._vel = self._vel * (1 - _FAST_A) + delta * _FAST_A
        self._fast = (fx, fy)

        sx = self._slow[0] * (1 - _SLOW_A) + fx * _SLOW_A
        sy = self._slow[1] * (1 - _SLOW_A) + fy * _SLOW_A
        self._slow = (sx, sy)

        w = min(_VEL_MAX, self._vel * _VEL_SCALE)
        ox = sx * (1 - w) + fx * w
        oy = sy * (1 - w) + fy * w
        return ox, oy
