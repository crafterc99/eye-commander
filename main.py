"""eye-commander — Jarvis-mode hand tracking control for macOS."""

import sys
import time
import threading

import cv2

import config
from core.camera import Camera
from core.hand_tracker import HandTracker
from core.hand_cursor import HandCursor
from core.gesture_detector import GestureDetector
from control import cursor, keyboard
from voice.listener import VoiceListener
from voice.commands import CommandDispatcher
from ui.overlay import StatusOverlay
from ui.preview import draw_frame

PREVIEW_WIN = "JARVIS  |  eye-commander  (Q to quit)"


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
        self._hand_tracker = HandTracker()
        self._hand_cursor = HandCursor(self._screen_w, self._screen_h)
        self._overlay = StatusOverlay()

        self._gesture = GestureDetector(
            on_click=self._click,
            on_right_click=self._right_click,
            on_double_click=self._double_click,
            on_scroll=cursor.scroll,
            on_drag_start=self._drag_start,
            on_drag_end=self._drag_end,
            on_pause=self._pause_tracking,
            on_resume=self._resume_tracking,
        )

        self._dispatcher = CommandDispatcher(
            on_calibrate=None,
            on_stop=self._pause_tracking,
            on_start=self._resume_tracking,
            on_quit=self._quit,
        )
        self._voice = VoiceListener(self._dispatcher.dispatch)

        self._running = False
        self._last_event = ""
        self._last_screen_pos = None
        self._frame_times = []

    # --- Mouse actions ---

    def _click(self):
        self._last_event = "click"
        cursor.left_click()

    def _right_click(self):
        self._last_event = "right click"
        cursor.right_click()

    def _double_click(self):
        self._last_event = "double click"
        cursor.double_click()

    def _drag_start(self):
        self._last_event = "drag start"
        from pynput.mouse import Button
        cursor.press(Button.left)

    def _drag_end(self):
        self._last_event = "drag end"
        from pynput.mouse import Button
        cursor.release(Button.left)

    def _pause_tracking(self):
        self._hand_cursor.set_enabled(False)
        self._overlay.update(mode="paused")
        self._last_event = "paused"
        print("\n[JARVIS] Tracking PAUSED  — open hand to resume")

    def _resume_tracking(self):
        self._hand_cursor.set_enabled(True)
        self._overlay.update(mode="tracking")
        self._last_event = "resumed"
        print("\n[JARVIS] Tracking RESUMED")

    def _quit(self):
        self._running = False

    # --- Main loop ---

    def run(self):
        print()
        print("=" * 60)
        print("  JARVIS  —  hand-controlled macOS")
        print()
        print("  Point index finger  →  cursor follows")
        print("  Pinch               →  left click")
        print("  Pinch + hold        →  drag")
        print("  Peace sign pinch    →  right click")
        print("  3 fingers + move    →  scroll")
        print("  Fist (hold 0.8s)   →  pause tracking")
        print("  Open hand           →  resume")
        print()
        print("  Voice: 'type ...' | 'click' | 'scroll up 3'")
        print("         'copy' | 'paste' | 'terminal' | 'quit'")
        print()
        print("  Press Q in preview window to quit")
        print("=" * 60)

        self._overlay.start()
        self._camera.start()
        self._voice.start()
        time.sleep(1.0)  # camera warm-up

        cv2.namedWindow(PREVIEW_WIN, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(PREVIEW_WIN, 720, 460)

        self._running = True

        try:
            while self._running:
                frame = self._camera.get_frame()
                if frame is None:
                    if cv2.waitKey(10) & 0xFF == ord('q'):
                        break
                    continue

                hand = self._hand_tracker.process(frame)

                # FPS
                now = time.time()
                self._frame_times.append(now)
                self._frame_times = [t for t in self._frame_times if now - t < 1.0]
                fps = len(self._frame_times)

                # Cursor movement
                screen_pos = self._hand_cursor.estimate(hand)
                if screen_pos is not None:
                    self._last_screen_pos = screen_pos
                    cursor.move(*screen_pos)

                # Gesture detection
                gesture_label = self._gesture.update(hand)
                if self._gesture.last_gesture:
                    self._last_event = self._gesture.last_gesture

                mode = "tracking" if self._hand_cursor.enabled else "paused"
                self._overlay.update(fps=fps, mode=mode, event=self._last_event)

                # Draw Jarvis HUD
                preview = draw_frame(
                    frame, hand, mode, fps, gesture_label,
                    self._last_screen_pos, self._screen_w, self._screen_h
                )
                if preview is not None:
                    cv2.imshow(PREVIEW_WIN, preview)

                key = cv2.waitKey(1) & 0xFF  # 1ms — keeps loop as fast as possible
                if key == ord('q'):
                    break
                elif key == ord('p'):
                    if self._hand_cursor.enabled:
                        self._pause_tracking()
                    else:
                        self._resume_tracking()

        except KeyboardInterrupt:
            print("\n[JARVIS] Interrupted.")
        finally:
            self._shutdown()

    def _shutdown(self):
        print("\n[JARVIS] Shutting down...")
        cv2.destroyAllWindows()
        self._camera.stop()
        self._voice.stop()
        self._hand_tracker.close()
        self._overlay.stop()
        print("[JARVIS] Offline.")


if __name__ == "__main__":
    EyeCommander().run()
