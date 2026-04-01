"""Terminal-based status display — no tkinter required."""

import threading
import sys


class StatusOverlay:
    def __init__(self):
        self._mode = "idle"
        self._fps = 0.0
        self._last_event = ""
        self._ear_l = 0.0
        self._ear_r = 0.0
        self._running = False
        self._lock = threading.Lock()
        self._dirty = False

    def start(self):
        self._running = True
        t = threading.Thread(target=self._print_loop, daemon=True)
        t.start()

    def _print_loop(self):
        import time
        while self._running:
            time.sleep(0.5)
            with self._lock:
                if self._dirty:
                    self._render()
                    self._dirty = False

    def _render(self):
        line = (f"\r[eye-commander] mode={self._mode:<12} "
                f"fps={self._fps:4.1f}  "
                f"EAR L={self._ear_l:.2f} R={self._ear_r:.2f}  "
                f"event={self._last_event:<20}")
        sys.stdout.write(line)
        sys.stdout.flush()

    def update(self, mode=None, fps=None, event=None, ear_l=None, ear_r=None):
        with self._lock:
            if mode is not None:
                self._mode = mode
            if fps is not None:
                self._fps = fps
            if event is not None:
                self._last_event = event
            if ear_l is not None:
                self._ear_l = ear_l
            if ear_r is not None:
                self._ear_r = ear_r
            self._dirty = True

    def stop(self):
        self._running = False
        print()  # newline after status line
