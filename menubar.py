"""macOS menu bar app for eye-commander / JARVIS hand tracking."""

import os
import subprocess
import sys
import rumps

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(PROJECT_DIR, ".venv", "bin", "python")
MAIN   = os.path.join(PROJECT_DIR, "main.py")

ICON_IDLE    = "✋"
ICON_RUNNING = "🤖"


class JarvisApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_IDLE, quit_button=None)
        self._proc = None
        self.menu = [
            rumps.MenuItem("▶  Launch JARVIS", callback=self.toggle),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

    @rumps.clicked("▶  Launch JARVIS")
    def toggle(self, sender):
        if self._proc is None or self._proc.poll() is not None:
            self._start()
        else:
            self._stop()

    def _start(self):
        self._proc = subprocess.Popen(
            [PYTHON, MAIN],
            cwd=PROJECT_DIR,
        )
        self.title = ICON_RUNNING
        self.menu["▶  Launch JARVIS"].title = "⏹  Stop JARVIS"
        rumps.notification("JARVIS", "Hand tracking active", "Point your finger to control the cursor.")

    def _stop(self):
        if self._proc:
            self._proc.terminate()
            self._proc = None
        self.title = ICON_IDLE
        self.menu["⏹  Stop JARVIS"].title = "▶  Launch JARVIS"
        rumps.notification("JARVIS", "Stopped", "Hand tracking offline.")

    def quit_app(self, _):
        self._stop()
        rumps.quit_application()


if __name__ == "__main__":
    JarvisApp().run()
