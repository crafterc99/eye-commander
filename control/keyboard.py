"""pynput keyboard control: type text, hotkeys, VS Code shortcuts."""

from pynput import keyboard as pynput_keyboard
from pynput.keyboard import Key, KeyCode

_controller = pynput_keyboard.Controller()


def type_text(text: str):
    _controller.type(text)


def press_key(key):
    """key: pynput Key enum or single-char string."""
    if isinstance(key, str) and len(key) == 1:
        key = KeyCode.from_char(key)
    _controller.press(key)
    _controller.release(key)


def hotkey(*keys):
    """Press a combination, e.g. hotkey(Key.cmd, 'c')."""
    resolved = []
    for k in keys:
        if isinstance(k, str) and len(k) == 1:
            resolved.append(KeyCode.from_char(k))
        else:
            resolved.append(k)
    for k in resolved:
        _controller.press(k)
    for k in reversed(resolved):
        _controller.release(k)


# --- Named shortcuts ---
def enter():
    press_key(Key.enter)


def escape():
    press_key(Key.esc)


def tab():
    press_key(Key.tab)


def space():
    press_key(Key.space)


def copy():
    hotkey(Key.cmd, 'c')


def paste():
    hotkey(Key.cmd, 'v')


def undo():
    hotkey(Key.cmd, 'z')


def save():
    hotkey(Key.cmd, 's')


def close():
    hotkey(Key.cmd, 'w')


def spotlight():
    hotkey(Key.cmd, Key.space)


def vscode_terminal():
    """Toggle integrated terminal: Ctrl+` """
    hotkey(Key.ctrl, KeyCode.from_char('`'))


def vscode_new_terminal():
    """New terminal: Ctrl+Shift+` """
    hotkey(Key.ctrl, Key.shift, KeyCode.from_char('`'))
