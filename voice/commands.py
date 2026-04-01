"""Voice command parser — maps recognized phrases to control actions."""

import re
from control import cursor, keyboard
import config


class CommandDispatcher:
    def __init__(self, on_calibrate=None, on_stop=None, on_start=None, on_quit=None,
                 on_dictate_start=None, on_dictate_stop=None):
        self._on_calibrate     = on_calibrate
        self._on_stop          = on_stop
        self._on_start         = on_start
        self._on_quit          = on_quit
        self._on_dictate_start = on_dictate_start
        self._on_dictate_stop  = on_dictate_stop
        self._dictating        = False

    def dispatch(self, phrase: str):
        phrase = phrase.strip().lower()
        print(f"[voice] '{phrase}'")

        # --- Dictation toggle (always checked first) ---
        if phrase in ("dictate", "start dictating", "dictation on"):
            if not self._dictating:
                self._dictating = True
                if self._on_dictate_start:
                    self._on_dictate_start()
            return
        if phrase in ("stop dictating", "stop dictation", "dictation off", "end dictation"):
            if self._dictating:
                self._dictating = False
                if self._on_dictate_stop:
                    self._on_dictate_stop()
            return

        # While dictating, ignore all other commands (Vosk mis-fires during speech)
        if self._dictating:
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
        if phrase in ("stop", "pause"):
            if self._on_stop:
                self._on_stop()
            return
        if phrase in ("start", "resume"):
            if self._on_start:
                self._on_start()
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

        # --- Type text ---
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

        print(f"[voice] Unrecognised command: '{phrase}'")
