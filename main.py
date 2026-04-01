"""eye-commander — hands-free macOS + VS Code control via eye tracking + voice."""

import sys
import time
import threading

import config
from core.camera import Camera
from core.face_tracker import FaceTracker
from core.gaze_estimator import GazeEstimator
from core.calibration import Calibration
from core.blink_detector import BlinkDetector
from core.head_pose import HeadPose
from control import cursor, keyboard
from voice.listener import VoiceListener
from voice.commands import CommandDispatcher
from ui.overlay import StatusOverlay
from ui.calibration_ui import CalibrationUI


def get_screen_size():
    """Get primary screen dimensions via AppKit (no tkinter)."""
    try:
        from AppKit import NSScreen
        screen = NSScreen.mainScreen()
        frame = screen.frame()
        return int(frame.size.width), int(frame.size.height)
    except Exception:
        # Fallback: ask OpenCV for a reasonable default
        return 1920, 1080


class EyeCommander:
    def __init__(self):
        self._screen_w, self._screen_h = get_screen_size()
        self._camera = Camera()
        self._face_tracker = FaceTracker()
        self._gaze = GazeEstimator()
        self._overlay = StatusOverlay()

        self._latest_face = None
        self._face_lock = threading.Lock()

        self._blink = BlinkDetector(self._on_blink)
        self._head_pose = HeadPose(self._on_gesture)

        self._dispatcher = CommandDispatcher(
            on_calibrate=self._start_calibration,
            on_stop=self._pause_tracking,
            on_start=self._resume_tracking,
            on_quit=self._quit,
        )
        self._voice = VoiceListener(self._dispatcher.dispatch)

        self._running = False
        self._calibrating = False

        # FPS tracking
        self._frame_times = []

    # --- Event handlers ---

    def _on_blink(self, event):
        self._overlay.update(event=f"blink:{event}")
        if event == "left":
            cursor.left_click()
        elif event == "right":
            cursor.right_click()
        elif event == "both":
            cursor.double_click()

    def _on_gesture(self, gesture):
        self._overlay.update(event=f"gesture:{gesture}")
        if gesture == "nod":
            keyboard.enter()
        elif gesture == "shake":
            keyboard.escape()
        elif gesture == "tilt_left":
            cursor.scroll(0, config.SCROLL_TICKS_DEFAULT)
        elif gesture == "tilt_right":
            cursor.scroll(0, -config.SCROLL_TICKS_DEFAULT)

    def _pause_tracking(self):
        self._gaze.set_enabled(False)
        self._overlay.update(mode="paused")
        print("[main] Gaze tracking paused.")

    def _resume_tracking(self):
        self._gaze.set_enabled(True)
        self._overlay.update(mode="tracking")
        print("[main] Gaze tracking resumed.")

    def _quit(self):
        print("[main] Quit command received.")
        self._running = False

    # --- Calibration ---

    def _start_calibration(self):
        self._calibrating = True
        self._overlay.update(mode="calibrating")
        print("[main] Starting calibration...")

        def face_ref():
            with self._face_lock:
                return self._latest_face

        cal_ui = CalibrationUI(self._screen_w, self._screen_h, self._on_calibration_done)
        cal_ui.start(face_ref)

    def _on_calibration_done(self, calibration: Calibration):
        self._gaze.set_calibration(calibration.get_data())
        self._calibrating = False
        self._gaze.set_enabled(True)
        self._overlay.update(mode="tracking")
        print("[main] Calibration complete. Tracking enabled.")

    def _load_or_run_calibration(self):
        data = Calibration.load()
        if data:
            print("[main] Loaded existing calibration.")
            self._gaze.set_calibration(data)
            self._gaze.set_enabled(True)
            self._overlay.update(mode="tracking")
        else:
            print("[main] No calibration found — starting calibration.")
            self._start_calibration()

    # --- Main loop ---

    def run(self):
        print("=" * 50)
        print("  eye-commander starting...")
        print("  Say 'quit' or press Ctrl+C to exit.")
        print("=" * 50)

        self._overlay.start()
        self._camera.start()
        self._voice.start()

        # Give camera a moment to warm up
        time.sleep(1.0)

        self._load_or_run_calibration()

        self._running = True
        self._overlay.update(mode="tracking")

        try:
            while self._running:
                frame = self._camera.get_frame()
                if frame is None:
                    time.sleep(0.01)
                    continue

                face = self._face_tracker.process(frame)

                with self._face_lock:
                    self._latest_face = face

                # FPS
                now = time.time()
                self._frame_times.append(now)
                self._frame_times = [t for t in self._frame_times if now - t < 1.0]
                fps = len(self._frame_times)

                if face is None:
                    self._overlay.update(fps=fps, mode="no face")
                    time.sleep(0.01)
                    continue

                # Blink detection
                ear_r, ear_l = self._blink.update(face)

                # Head pose
                self._head_pose.update(face)

                # Gaze → cursor
                screen_pos = self._gaze.estimate(face)
                if screen_pos is not None:
                    cursor.move(*screen_pos)

                mode = "tracking" if self._gaze.enabled else "paused"
                self._overlay.update(fps=fps, mode=mode, ear_l=ear_l, ear_r=ear_r)

                time.sleep(0.005)  # ~200fps ceiling, camera limits actual rate

        except KeyboardInterrupt:
            print("\n[main] Interrupted.")
        finally:
            self._shutdown()

    def _shutdown(self):
        print("[main] Shutting down...")
        self._camera.stop()
        self._voice.stop()
        self._face_tracker.close()
        self._overlay.stop()
        print("[main] Bye.")


if __name__ == "__main__":
    EyeCommander().run()
