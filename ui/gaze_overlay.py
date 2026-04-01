"""Translucent gaze highlight overlay for macOS.

Creates a borderless, click-through, always-on-top NSWindow that draws a
soft cyan glow rect over whatever UI element the user is looking at.

Element bounds are fetched from the macOS Accessibility API (requires
Accessibility permission in System Prefs). Falls back to a fixed-size
highlight if permission not granted.

Call order:
  overlay = GazeOverlay()          # must be AFTER cv2.namedWindow()
  overlay.update(gx, gy)           # each frame, give gaze screen pos
  overlay.tick()                   # each frame, pump Cocoa run loop
  overlay.close()                  # on shutdown
"""

import ctypes
import ctypes.util
import threading
import time

# --- Accessibility API ---
try:
    from ApplicationServices import (
        AXUIElementCreateSystemWide,
        AXUIElementCopyElementAtPosition,
        AXUIElementCopyAttributeValue,
        kAXPositionAttribute,
        kAXSizeAttribute,
    )
    _ax_available = True
except ImportError:
    _ax_available = False

_FALLBACK_W = 180
_FALLBACK_H = 90

# ctypes helpers to unpack AXValue → CGPoint / CGSize
_appservices = ctypes.cdll.LoadLibrary(
    '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices'
)

class _CGPoint(ctypes.Structure):
    _fields_ = [('x', ctypes.c_double), ('y', ctypes.c_double)]

class _CGSize(ctypes.Structure):
    _fields_ = [('width', ctypes.c_double), ('height', ctypes.c_double)]

# kAXValueCGPointType = 1, kAXValueCGSizeType = 2
_appservices.AXValueGetValue.restype  = ctypes.c_bool
_appservices.AXValueGetValue.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]


def _ax_element_rect(x: float, y: float):
    """Returns (ex, ey, ew, eh) of the AX element at screen point, or None."""
    if not _ax_available:
        return None
    try:
        syswide = AXUIElementCreateSystemWide()
        err, elem = AXUIElementCopyElementAtPosition(syswide, float(x), float(y), None)
        if err != 0 or elem is None:
            return None
        err1, pos_val  = AXUIElementCopyAttributeValue(elem, kAXPositionAttribute, None)
        err2, size_val = AXUIElementCopyAttributeValue(elem, kAXSizeAttribute, None)
        if err1 != 0 or err2 != 0 or pos_val is None or size_val is None:
            return None
        # Extract raw pointer from PyObjC wrapper
        pt = _CGPoint()
        sz = _CGSize()
        pos_ptr  = ctypes.cast(id(pos_val),  ctypes.c_void_p)
        size_ptr = ctypes.cast(id(size_val), ctypes.c_void_p)
        ok1 = _appservices.AXValueGetValue(pos_ptr.value,  1, ctypes.byref(pt))
        ok2 = _appservices.AXValueGetValue(size_ptr.value, 2, ctypes.byref(sz))
        if not ok1 or not ok2:
            return None
        w, h = sz.width, sz.height
        if w < 4 or h < 4 or w > 3000 or h > 2000:
            return None
        return pt.x, pt.y, w, h
    except Exception:
        return None


# --- Element rect cache (poll slowly to avoid hammering AX) ---
class _RectCache:
    POLL_INTERVAL = 0.08   # seconds between AX lookups

    def __init__(self):
        self._last_poll = 0.0
        self._last_pos  = None
        self._cached    = None

    def get(self, x: float, y: float):
        now = time.monotonic()
        if (now - self._last_poll < self.POLL_INTERVAL
                and self._last_pos is not None
                and abs(x - self._last_pos[0]) < 40
                and abs(y - self._last_pos[1]) < 40):
            return self._cached
        self._last_poll = now
        self._last_pos  = (x, y)
        self._cached    = _ax_element_rect(x, y)
        return self._cached


# --- NSWindow overlay ---

class GazeOverlay:
    def __init__(self):
        self._window  = None
        self._view    = None
        self._visible = False
        self._cache   = _RectCache()
        self._screen_h = 0
        self._init_window()

    def _init_window(self):
        try:
            import objc
            from AppKit import (
                NSWindow, NSView, NSColor,
                NSBorderlessWindowMask, NSBackingStoreBuffered,
                NSWindowCollectionBehaviorCanJoinAllSpaces,
                NSWindowCollectionBehaviorStationary,
                NSFloatingWindowLevel,
                NSBezierPath,
                NSScreen,
            )
            from Foundation import NSMakeRect

            self._screen_h = NSScreen.mainScreen().frame().size.height

            # Build custom view class at runtime
            GazeHighlightView = objc.runtime.NSView

            rect = NSMakeRect(0, 0, _FALLBACK_W, _FALLBACK_H)
            win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                rect,
                NSBorderlessWindowMask,
                NSBackingStoreBuffered,
                False,
            )
            win.setBackgroundColor_(NSColor.clearColor())
            win.setOpaque_(False)
            win.setIgnoresMouseEvents_(True)
            win.setLevel_(NSFloatingWindowLevel + 1)
            win.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorStationary
            )
            win.setAlphaValue_(1.0)

            self._window   = win
            self._ns_color = NSColor
            self._ns_path  = NSBezierPath
            self._ns_rect  = NSMakeRect
            self._ns_screen_h = self._screen_h
            print("[gaze_overlay] Overlay window created.")
        except Exception as e:
            print(f"[gaze_overlay] Could not create overlay: {e}")

    def update(self, gx: float, gy: float):
        """Position overlay at gaze point (gx,gy) in screen coordinates."""
        if self._window is None:
            return

        rect = self._cache.get(gx, gy)
        if rect:
            ex, ey, ew, eh = rect
        else:
            ex = gx - _FALLBACK_W / 2
            ey = gy - _FALLBACK_H / 2
            ew, eh = _FALLBACK_W, _FALLBACK_H

        # Cocoa uses bottom-left origin; screen coords are top-left
        cocoa_y = self._screen_h - ey - eh
        try:
            from Foundation import NSMakeRect
            self._window.setFrame_display_(
                NSMakeRect(ex, cocoa_y, ew, eh), False
            )
            self._window.setContentView_(
                _make_highlight_view(ew, eh, self._ns_color, self._ns_path, self._ns_rect)
            )
            if not self._visible:
                self._window.orderFront_(None)
                self._visible = True
        except Exception:
            pass

    def hide(self):
        if self._window and self._visible:
            try:
                self._window.orderOut_(None)
            except Exception:
                pass
            self._visible = False

    def tick(self):
        """Pump Cocoa run loop — call every frame to keep overlay drawn."""
        try:
            from Foundation import NSRunLoop, NSDate
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.0)
            )
        except Exception:
            pass

    def close(self):
        self.hide()


def _make_highlight_view(w, h, NSColor, NSBezierPath, NSMakeRect):
    """Return a freshly-drawn NSView with the gaze highlight painted in."""
    import objc

    # We draw directly into the view's layer via a closure trick:
    # Create a plain NSView subclass and override drawRect_ using objc
    try:
        from AppKit import NSView, NSGraphicsContext

        class _GlowView(NSView):
            def drawRect_(self, dirty_rect):
                ctx = NSGraphicsContext.currentContext()
                if ctx is None:
                    return
                r = self.bounds()
                # Outer glow
                glow = NSColor.colorWithRed_green_blue_alpha_(0.0, 0.82, 1.0, 0.18)
                glow.setFill()
                path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(r, 10, 10)
                path.fill()
                # Fill
                fill = NSColor.colorWithRed_green_blue_alpha_(0.05, 0.70, 1.0, 0.28)
                fill.setFill()
                inner_r = NSMakeRect(r.origin.x + 2, r.origin.y + 2,
                                     r.size.width - 4, r.size.height - 4)
                path2 = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(inner_r, 8, 8)
                path2.fill()
                # Border
                border = NSColor.colorWithRed_green_blue_alpha_(0.0, 0.92, 1.0, 0.85)
                border.setStroke()
                path2.setLineWidth_(1.5)
                path2.stroke()

        view = _GlowView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
        return view
    except Exception:
        from AppKit import NSView
        return NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
