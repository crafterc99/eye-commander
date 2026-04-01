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
from core.app_detector import get_active_app
from core.gaze_cursor import GazeCursor
from control import cursor, keyboard
from voice.listener import VoiceListener
from voice.commands import CommandDispatcher
from voice.dictation import DictationManager
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
        self._camera       = Camera()
        self._hand_tracker = HandTracker()
        self._hand_cursor  = HandCursor(self._screen_w, self._screen_h)
        self._overlay      = StatusOverlay()

        # Dictation state
        self._dictation    = DictationManager(
            on_partial = self._on_dictation_partial,
            on_final   = self._on_dictation_final,
            on_status  = self._on_dictation_status,
        )
        self._dict_status  = "idle"   # idle | active | composing
        self._partial_text = ""       # live partial from Wispr

        # Eye gaze cursor (GazeTracking)
        self._gaze_cursor  = GazeCursor(self._screen_w, self._screen_h)
        self._gaze_overlay = None          # created after cv2.namedWindow
        # "hand" = hand drives cursor (default), "gaze" = eyes drive cursor
        self._cursor_source = "hand"

        # Active app (polled every ~30 frames)
        self._active_app   = ""
        self._app_tick     = 0

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
            on_calibrate   = None,
            on_stop        = self._pause_tracking,
            on_start       = self._resume_tracking,
            on_quit        = self._quit,
            on_dictate_start = self._dictation.begin_immediate,
            on_dictate_stop  = self._dictation.end,
            on_type_start  = self._dictation.begin_compose,
            on_submit      = self._dictation.submit,
            on_cancel      = self._dictation.cancel,
            on_eye_mode    = lambda: self._set_cursor_source("gaze"),
            on_hand_mode   = lambda: self._set_cursor_source("hand"),
            on_calibrate_gaze = self._gaze_cursor.recalibrate,
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

    # --- Dictation callbacks ---

    def _on_dictation_partial(self, text: str):
        self._partial_text = text

    def _on_dictation_final(self, text: str):
        self._partial_text = ""
        self._last_event = f"'{text[:30]}...'" if len(text) > 30 else f"'{text}'"

    def _set_cursor_source(self, source: str):
        """Switch cursor between 'hand' and 'gaze'."""
        self._cursor_source = source
        self._last_event = f"cursor: {source}"
        print(f"\n[JARVIS] Cursor → {source.upper()}")

    def _on_dictation_status(self, status: str):
        self._dict_status = status
        # Keep CommandDispatcher in sync
        self._dispatcher.set_composing(status == "composing")
        self._dispatcher.set_dictating(status == "active")
        if status == "idle":
            self._partial_text = ""

    # --- Tracking control ---

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
        print("  Point index finger   →  cursor follows")
        print("  Pinch                →  left click")
        print("  Pinch + hold 0.35s   →  drag")
        print("  Peace + spread       →  right click")
        print("  3 fingers + move     →  continuous scroll")
        print("  Fist (hold 0.45s)    →  pause tracking")
        print("  Open palm (8 frames) →  resume")
        print()
        print("  Eye gaze             →  moves cursor (no clicks) + glow overlay")
        print("                          look straight ahead for 1.5s to calibrate")
        print()
        print("  Voice: 'type'        →  compose mode (say, then 'submit'/'cancel')")
        print("         'dictate'     →  live dictation (types as you speak)")
        print("         'eye mode'    →  gaze drives cursor (no clicks)")
        print("         'hand mode'   →  hand drives cursor (default)")
        print("         'calibrate gaze' →  reset gaze calibration")
        print("         'click' 'copy' 'paste' 'scroll up' 'quit'")
        print()
        print("  Press Q in preview window to quit")
        print("=" * 60)

        self._overlay.start()
        self._camera.start()
        self._voice.start()
        self._dictation.start()
        time.sleep(1.0)  # camera warm-up

        cv2.namedWindow(PREVIEW_WIN, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(PREVIEW_WIN, 720, 460)

        # Gaze overlay — must init AFTER cv2.namedWindow (which starts NSApp)
        try:
            from ui.gaze_overlay import GazeOverlay
            self._gaze_overlay = GazeOverlay()
        except Exception as e:
            print(f"[gaze_overlay] Disabled: {e}")

        self._running = True

        try:
            while self._running:
                frame = self._camera.get_frame()
                if frame is None:
                    if cv2.waitKey(10) & 0xFF == ord('q'):
                        break
                    continue

                hand = self._hand_tracker.process(frame)

                # Gaze tracking (background thread — submit frame, read latest)
                self._gaze_cursor.submit_frame(frame)
                gaze_pos = self._gaze_cursor.latest_pos()

                # Update gaze overlay regardless of cursor source
                if gaze_pos:
                    gx, gy = int(gaze_pos[0]), int(gaze_pos[1])
                    if self._gaze_overlay:
                        self._gaze_overlay.update(gx, gy)
                elif self._gaze_overlay:
                    self._gaze_overlay.hide()

                # Pump Cocoa run loop so overlay renders
                if self._gaze_overlay:
                    self._gaze_overlay.tick()

                # FPS
                now = time.time()
                self._frame_times.append(now)
                self._frame_times = [t for t in self._frame_times if now - t < 1.0]
                fps = len(self._frame_times)

                # Cursor movement — ONE source only
                if self._cursor_source == "gaze" and gaze_pos:
                    self._last_screen_pos = (int(gaze_pos[0]), int(gaze_pos[1]))
                    cursor.move(*self._last_screen_pos)
                elif self._cursor_source == "hand":
                    screen_pos = self._hand_cursor.estimate(hand)
                    if screen_pos is not None:
                        self._last_screen_pos = screen_pos
                        cursor.move(*screen_pos)

                # Gesture detection
                gesture_label = self._gesture.update(hand)
                if self._gesture.last_gesture:
                    self._last_event = self._gesture.last_gesture

                # Active app (every ~30 frames)
                self._app_tick += 1
                if self._app_tick >= 30:
                    self._app_tick  = 0
                    self._active_app = get_active_app()

                # Mode label
                mode = self._dict_status if self._dict_status != "idle" else (
                    "tracking" if self._hand_cursor.enabled else "paused"
                )
                self._overlay.update(fps=fps, mode=mode, event=self._last_event)

                # Build HUD state
                hud_state = self._gesture.get_hud_state()
                hud_state.update({
                    "compose_text":  self._dictation.compose_text,
                    "partial_text":  self._partial_text,
                    "active_app":    self._active_app,
                    "dict_status":   self._dict_status,
                    "cursor_source": self._cursor_source,
                })

                preview = draw_frame(
                    frame, hand, mode, fps, gesture_label,
                    self._last_screen_pos, self._screen_w, self._screen_h,
                    hud_state=hud_state,
                )
                if preview is not None:
                    cv2.imshow(PREVIEW_WIN, preview)

                key = cv2.waitKey(1) & 0xFF
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
        if self._gaze_overlay:
            self._gaze_overlay.close()
        self._camera.stop()
        self._voice.stop()
        self._hand_tracker.close()
        self._overlay.stop()
        self._dictation.stop()
        print("[JARVIS] Offline.")


if __name__ == "__main__":
    EyeCommander().run()
