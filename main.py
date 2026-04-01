"""eye-commander — hands-free macOS + VS Code control via eye tracking + voice."""

import sys
import time
import threading

import cv2

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
from ui.preview import draw_tracking


PREVIEW_WIN = "eye-commander  |  q=quit"


def get_screen_size():
    try:
        from AppKit import NSScreen
        screen = NSScreen.mainScreen()
        frame = screen.frame()
        return int(frame.size.width), int(frame.size.height)
    except Exception:
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
        self._last_event = ""
        self._last_gaze = None

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
        self._frame_times = []
        self._ear_l = 0.0
        self._ear_r = 0.0

    # --- Event handlers ---

    def _on_blink(self, event):
        self._last_event = f"BLINK:{event}"
        self._overlay.update(event=self._last_event)
        if event == "left":
            cursor.left_click()
        elif event == "right":
            cursor.right_click()
        elif event == "both":
            cursor.double_click()

    def _on_gesture(self, gesture):
        self._last_event = f"GESTURE:{gesture}"
        self._overlay.update(event=self._last_event)
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
        print("\n[eye-commander] Gaze tracking PAUSED  (say 'start' to resume)")

    def _resume_tracking(self):
        self._gaze.set_enabled(True)
        self._overlay.update(mode="tracking")
        print("\n[eye-commander] Gaze tracking RESUMED")

    def _quit(self):
        self._running = False

    # --- Calibration ---

    def _start_calibration(self):
        self._calibrating = True
        self._overlay.update(mode="calibrating")
        print("\n[eye-commander] Starting 9-point calibration — look at each dot for 3 seconds")

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
        print("\n[eye-commander] Calibration done! Cursor now follows your eyes.")

    def _load_or_run_calibration(self):
        data = Calibration.load()
        if data:
            print("[eye-commander] Loaded calibration — cursor tracking active.")
            self._gaze.set_calibration(data)
            self._gaze.set_enabled(True)
            self._overlay.update(mode="tracking")
        else:
            print("[eye-commander] No calibration found — starting calibration...")
            self._start_calibration()

    # --- Main loop ---

    def run(self):
        print()
        print("=" * 56)
        print("  eye-commander")
        print("  Eyes  : look at screen to move cursor")
        print("  Blink : L eye = left click | R eye = right click")
        print("  Head  : nod=Enter | shake=Esc | tilt=scroll")
        print("  Voice : 'type hello' | 'click' | 'scroll up 3'")
        print("  Voice : 'calibrate' | 'stop' | 'quit'")
        print("  Keys  : press Q in preview window to quit")
        print("=" * 56)

        self._overlay.start()
        self._camera.start()
        self._voice.start()

        time.sleep(1.0)  # camera warm-up

        self._load_or_run_calibration()

        # Set up OpenCV preview window
        cv2.namedWindow(PREVIEW_WIN, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(PREVIEW_WIN, 640, 400)

        self._running = True

        try:
            while self._running:
                frame = self._camera.get_frame()
                if frame is None:
                    if cv2.waitKey(10) & 0xFF == ord('q'):
                        break
                    continue

                face = self._face_tracker.process(frame)

                with self._face_lock:
                    self._latest_face = face

                # FPS
                now = time.time()
                self._frame_times.append(now)
                self._frame_times = [t for t in self._frame_times if now - t < 1.0]
                fps = len(self._frame_times)

                if face is not None:
                    # Blink detection
                    self._ear_r, self._ear_l = self._blink.update(face)

                    # Head pose gestures
                    self._head_pose.update(face)

                    # Gaze → cursor
                    screen_pos = self._gaze.estimate(face)
                    if screen_pos is not None:
                        self._last_gaze = screen_pos
                        cursor.move(*screen_pos)

                mode = "tracking" if self._gaze.enabled else "paused"
                if self._calibrating:
                    mode = "calibrating"

                self._overlay.update(fps=fps, mode=mode, ear_l=self._ear_l, ear_r=self._ear_r)

                # Draw preview
                preview = draw_tracking(
                    frame, face,
                    self._ear_l, self._ear_r,
                    mode, fps, self._last_event,
                    self._last_gaze, self._screen_w, self._screen_h
                )
                if preview is not None:
                    cv2.imshow(PREVIEW_WIN, preview)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('c'):
                    threading.Thread(target=self._start_calibration, daemon=True).start()
                elif key == ord('p'):
                    if self._gaze.enabled:
                        self._pause_tracking()
                    else:
                        self._resume_tracking()

        except KeyboardInterrupt:
            print("\n[eye-commander] Interrupted.")
        finally:
            self._shutdown()

    def _shutdown(self):
        print("\n[eye-commander] Shutting down...")
        cv2.destroyAllWindows()
        self._camera.stop()
        self._voice.stop()
        self._face_tracker.close()
        self._overlay.stop()
        print("[eye-commander] Bye.")


if __name__ == "__main__":
    EyeCommander().run()
