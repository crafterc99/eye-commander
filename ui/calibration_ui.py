"""OpenCV-based full-screen calibration window with 9 sequential dots."""

import threading
import time
import numpy as np
import cv2
import config
from core.calibration import Calibration, GRID_POSITIONS


class CalibrationUI:
    def __init__(self, screen_w, screen_h, on_complete):
        self._sw = screen_w
        self._sh = screen_h
        self._on_complete = on_complete
        self._calibration = Calibration(screen_w, screen_h)
        self._face_tracker_ref = None

    def start(self, face_tracker_ref):
        self._face_tracker_ref = face_tracker_ref
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        win = "eye-commander calibration"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

        dots = self._calibration.dot_screen_positions()
        frame_size = (640, 480)

        for i, (dx, dy) in enumerate(dots):
            samples = []
            canvas = np.zeros((self._sh, self._sw, 3), dtype=np.uint8)
            cv2.circle(canvas, (dx, dy), 18, (0, 0, 220), -1)
            cv2.circle(canvas, (dx, dy), 8, (255, 255, 255), -1)
            label = f"Look at the dot  ({i+1}/9)"
            cv2.putText(canvas, label,
                        (self._sw // 2 - 180, self._sh - 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
            cv2.putText(canvas, "Hold still...",
                        (self._sw // 2 - 90, self._sh - 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (120, 120, 120), 1)
            cv2.imshow(win, canvas)
            cv2.waitKey(1)

            deadline = time.time() + config.CALIBRATION_DWELL_SECS
            while time.time() < deadline:
                face = self._face_tracker_ref()
                if face is not None:
                    rx, ry = face.iris_right
                    lx, ly = face.iris_left
                    samples.append(((rx + lx) / 2.0, (ry + ly) / 2.0))
                    frame_size = face.frame_size
                # flash dot green when collecting
                remaining = deadline - time.time()
                pulse = np.zeros((self._sh, self._sw, 3), dtype=np.uint8)
                color = (0, int(180 * (remaining / config.CALIBRATION_DWELL_SECS) + 75), 0)
                cv2.circle(pulse, (dx, dy), 18, color, -1)
                cv2.circle(pulse, (dx, dy), 8, (255, 255, 255), -1)
                cv2.putText(pulse, label,
                            (self._sw // 2 - 180, self._sh - 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
                cv2.putText(pulse, f"Collecting... {len(samples)} samples",
                            (self._sw // 2 - 160, self._sh - 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 200, 100), 1)
                cv2.imshow(win, pulse)
                cv2.waitKey(50)

            self._calibration.record_sample(i, samples, frame_size[0], frame_size[1])
            # brief white flash between dots
            flash = np.ones((self._sh, self._sw, 3), dtype=np.uint8) * 40
            cv2.imshow(win, flash)
            cv2.waitKey(300)

        cv2.destroyWindow(win)
        self._calibration.save()
        self._on_complete(self._calibration)
