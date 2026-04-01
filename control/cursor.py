"""pynput mouse control: move, click, scroll, drag."""

from pynput import mouse as pynput_mouse
from pynput.mouse import Button

_controller = pynput_mouse.Controller()


def move(x, y):
    _controller.position = (int(x), int(y))


def left_click(x=None, y=None):
    if x is not None:
        move(x, y)
    _controller.click(Button.left, 1)


def right_click(x=None, y=None):
    if x is not None:
        move(x, y)
    _controller.click(Button.right, 1)


def double_click(x=None, y=None):
    if x is not None:
        move(x, y)
    _controller.click(Button.left, 2)


def scroll(dx=0, dy=0):
    _controller.scroll(dx, dy)


def press(button=Button.left):
    _controller.press(button)


def release(button=Button.left):
    _controller.release(button)
