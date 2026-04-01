"""Small tkinter status HUD — shows mode, FPS, last event."""

import tkinter as tk
import threading
import time


class StatusOverlay:
    def __init__(self):
        self._mode = "idle"
        self._fps = 0.0
        self._last_event = ""
        self._ear_l = 0.0
        self._ear_r = 0.0
        self._root = None
        self._labels = {}
        self._running = False

    def start(self):
        t = threading.Thread(target=self._run_ui, daemon=True)
        t.start()

    def _run_ui(self):
        self._root = tk.Tk()
        self._root.title("eye-commander")
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.85)
        self._root.configure(bg="#1a1a1a")
        self._root.geometry("260x160+20+20")
        self._root.resizable(False, False)

        pad = {"padx": 8, "pady": 2}
        style = {"bg": "#1a1a1a", "fg": "#f0f0f0", "font": ("Courier", 11)}

        self._labels["title"] = tk.Label(self._root, text="eye-commander", bg="#1a1a1a", fg="#FFA500", font=("Courier", 12, "bold"))
        self._labels["title"].pack(**pad)

        for key, label in [("mode", "Mode: idle"), ("fps", "FPS: 0"), ("ear", "EAR: --"), ("event", "Event: --")]:
            lbl = tk.Label(self._root, text=label, **style)
            lbl.pack(anchor="w", **pad)
            self._labels[key] = lbl

        hint = tk.Label(self._root, text='Say "quit" to exit', bg="#1a1a1a", fg="#888888", font=("Courier", 9))
        hint.pack(**pad)

        self._running = True
        self._root.after(200, self._refresh)
        self._root.mainloop()

    def _refresh(self):
        if not self._running:
            return
        self._labels["mode"].config(text=f"Mode: {self._mode}")
        self._labels["fps"].config(text=f"FPS: {self._fps:.1f}")
        self._labels["ear"].config(text=f"EAR L:{self._ear_l:.2f} R:{self._ear_r:.2f}")
        self._labels["event"].config(text=f"Event: {self._last_event}")
        self._root.after(200, self._refresh)

    def update(self, mode=None, fps=None, event=None, ear_l=None, ear_r=None):
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

    def stop(self):
        self._running = False
        if self._root:
            try:
                self._root.destroy()
            except Exception:
                pass
