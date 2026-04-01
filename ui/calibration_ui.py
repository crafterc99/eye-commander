"""Full-screen tkinter calibration window with 9 sequential red dots."""

import tkinter as tk
import threading
import time
import config
from core.calibration import Calibration, GRID_POSITIONS


class CalibrationUI:
    def __init__(self, screen_w, screen_h, on_complete):
        """
        on_complete(calibration: Calibration) called when all 9 dots done.
        """
        self._sw = screen_w
        self._sh = screen_h
        self._on_complete = on_complete
        self._calibration = Calibration(screen_w, screen_h)
        self._dot_index = 0
        self._collecting = False
        self._samples = []
        self._frame_size = (640, 480)
        self._root = None
        self._canvas = None
        self._dot_id = None
        self._label_id = None

    def start(self, face_tracker_ref):
        """face_tracker_ref: a callable that returns the latest FaceResult or None."""
        self._face_tracker_ref = face_tracker_ref
        t = threading.Thread(target=self._run_ui, daemon=True)
        t.start()

    def _run_ui(self):
        self._root = tk.Tk()
        self._root.attributes("-fullscreen", True)
        self._root.configure(bg="black")
        self._root.title("Calibration")
        self._root.lift()
        self._root.focus_force()

        self._canvas = tk.Canvas(self._root, bg="black", highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        self._root.after(500, self._show_dot)
        self._root.mainloop()

    def _show_dot(self):
        if self._dot_index >= len(GRID_POSITIONS):
            self._finish()
            return

        self._canvas.delete("all")
        fx, fy = GRID_POSITIONS[self._dot_index]
        x = int(fx * self._sw)
        y = int(fy * self._sh)
        r = 15

        self._dot_id = self._canvas.create_oval(x - r, y - r, x + r, y + r, fill="red", outline="")
        n = self._dot_index + 1
        self._label_id = self._canvas.create_text(
            self._sw // 2, self._sh - 40,
            text=f"Look at the dot  ({n}/9)",
            fill="white", font=("Arial", 18)
        )

        self._samples = []
        self._collecting = True
        collect_end = time.time() + config.CALIBRATION_DWELL_SECS
        self._root.after(100, lambda: self._collect_loop(collect_end))

    def _collect_loop(self, collect_end):
        if not self._collecting:
            return
        face = self._face_tracker_ref()
        if face is not None:
            rx, ry = face.iris_right
            lx, ly = face.iris_left
            avg_x = (rx + lx) / 2.0
            avg_y = (ry + ly) / 2.0
            self._samples.append((avg_x, avg_y))
            self._frame_size = face.frame_size

        remaining = collect_end - time.time()
        if remaining > 0:
            self._root.after(50, lambda: self._collect_loop(collect_end))
        else:
            self._collecting = False
            self._calibration.record_sample(
                self._dot_index, self._samples,
                self._frame_size[0], self._frame_size[1]
            )
            self._dot_index += 1
            self._root.after(300, self._show_dot)

    def _finish(self):
        self._calibration.save()
        self._root.destroy()
        self._on_complete(self._calibration)
