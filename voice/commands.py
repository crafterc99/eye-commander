"""Voice command parser — maps recognized phrases to control actions."""

import re
from control import cursor, keyboard
import config


class CommandDispatcher:
    def __init__(self, on_calibrate=None, on_stop=None, on_start=None, on_quit=None,
                 on_dictate_start=None, on_dictate_stop=None,
                 on_type_start=None, on_submit=None, on_cancel=None,
                 on_eye_mode=None, on_hand_mode=None, on_calibrate_gaze=None):
        self._on_calibrate    = on_calibrate
        self._on_stop         = on_stop
        self._on_start        = on_start
        self._on_quit         = on_quit
        self._on_dictate_start = on_dictate_start
        self._on_dictate_stop  = on_dictate_stop
        self._on_type_start   = on_type_start   # begin compose mode
        self._on_submit       = on_submit
        self._on_cancel       = on_cancel
        self._on_eye_mode     = on_eye_mode
        self._on_hand_mode    = on_hand_mode
        self._on_calibrate_gaze = on_calibrate_gaze
        self._dictating       = False  # immediate dictation mode
        self._composing       = False  # compose mode

    def set_composing(self, val: bool):
        """Called by main to keep dispatcher in sync with compose state."""
        self._composing = val

    def set_dictating(self, val: bool):
        self._dictating = val

    def dispatch(self, phrase: str):
        phrase = phrase.strip().lower()
        print(f"[voice] '{phrase}'")

        # --- Compose mode: only submit/cancel break through ---
        if self._composing:
            if phrase in ("submit", "send", "enter", "done"):
                self._composing = False
                if self._on_submit:
                    self._on_submit()
            elif phrase in ("cancel", "nevermind", "never mind", "clear", "discard"):
                self._composing = False
                if self._on_cancel:
                    self._on_cancel()
            # Everything else is speech being transcribed — ignore from Vosk
            return

        # --- Immediate dictation mode: only stop-words break through ---
        if self._dictating:
            if phrase in ("stop dictating", "stop dictation", "dictation off", "end dictation", "stop"):
                self._dictating = False
                if self._on_dictate_stop:
                    self._on_dictate_stop()
            return

        # --- Compose trigger: "type" alone → compose mode ---
        if phrase == "type":
            self._composing = True
            if self._on_type_start:
                self._on_type_start()
            return

        # --- Immediate dictation trigger ---
        if phrase in ("dictate", "start dictating", "dictation on"):
            self._dictating = True
            if self._on_dictate_start:
                self._on_dictate_start()
            return

        if phrase in ("stop dictating", "stop dictation", "dictation off", "end dictation"):
            self._dictating = False
            if self._on_dictate_stop:
                self._on_dictate_stop()
            return

        # --- App control ---
        if phrase in ("quit", "exit", "stop listening"):
            if self._on_quit:
                self._on_quit()
            return
        if phrase == "calibrate":
            if self._on_calibrate:
                self._on_calibrate()
            return
        if phrase in ("pause"):
            if self._on_stop:
                self._on_stop()
            return
        if phrase in ("start", "resume"):
            if self._on_start:
                self._on_start()
            return

        # --- Cursor source ---
        if phrase in ("eye mode", "eye tracking", "gaze mode", "use eyes"):
            if self._on_eye_mode:
                self._on_eye_mode()
            return
        if phrase in ("hand mode", "hand tracking", "use hand", "use hands"):
            if self._on_hand_mode:
                self._on_hand_mode()
            return
        if phrase in ("calibrate gaze", "calibrate eyes", "recalibrate"):
            if self._on_calibrate_gaze:
                self._on_calibrate_gaze()
            return

        # --- Mouse ---
        if phrase in ("click", "left click"):
            cursor.left_click()
            return
        if phrase == "right click":
            cursor.right_click()
            return
        if phrase == "double click":
            cursor.double_click()
            return

        # --- Scroll ---
        m = re.match(r"scroll (up|down)(?: (\d+))?", phrase)
        if m:
            direction = m.group(1)
            ticks = int(m.group(2)) if m.group(2) else config.SCROLL_TICKS_DEFAULT
            dy = ticks if direction == "up" else -ticks
            cursor.scroll(0, dy)
            return

        # --- Type text inline: "type hello world" ---
        m = re.match(r"type (.+)", phrase)
        if m:
            keyboard.type_text(m.group(1))
            return

        # --- Key presses ---
        if "press enter" in phrase or phrase == "enter":
            keyboard.enter()
            return
        if "press tab" in phrase or phrase == "tab":
            keyboard.tab()
            return
        if "press escape" in phrase or phrase in ("escape", "esc"):
            keyboard.escape()
            return
        if "press space" in phrase or phrase == "space":
            keyboard.space()
            return

        # --- macOS / VS Code shortcuts ---
        if phrase == "copy":
            keyboard.copy()
            return
        if phrase == "paste":
            keyboard.paste()
            return
        if phrase == "undo":
            keyboard.undo()
            return
        if phrase == "save":
            keyboard.save()
            return
        if phrase == "close":
            keyboard.close()
            return
        if phrase == "spotlight":
            keyboard.spotlight()
            return
        if phrase == "terminal":
            keyboard.vscode_terminal()
            return
        if phrase in ("new terminal", "open terminal"):
            keyboard.vscode_new_terminal()
            return

        print(f"[voice] Unrecognised: '{phrase}'")
