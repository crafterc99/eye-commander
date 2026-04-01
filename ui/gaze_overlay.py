"""Translucent gaze highlight overlay for macOS.

Transparent, click-through, always-on-top NSWindow that draws a soft
cyan glow rect wherever the user is looking.

IMPORTANT: _GlowView is defined at module level so the ObjC class is
registered exactly once. Never define NSView subclasses inside functions.

Usage:
  overlay = GazeOverlay()      # after cv2.namedWindow()
  overlay.update(gx, gy)       # each frame
  overlay.tick()               # each frame — pumps Cocoa run loop
  overlay.close()              # on shutdown
"""

import time

# ── ObjC view class — registered ONCE at import time ──────────────────────────
try:
    import objc
    from AppKit import (
        NSView, NSBezierPath, NSColor,
        NSWindow, NSBorderlessWindowMask, NSBackingStoreBuffered,
        NSFloatingWindowLevel,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorStationary,
        NSScreen,
    )
    from Foundation import NSMakeRect, NSRunLoop, NSDate

    class _GlowView(NSView):
        """Single persistent view — only position/size changes, not class."""
        def drawRect_(self, dirty_rect):
            r = self.bounds()
            rx, ry, rw, rh = r.origin.x, r.origin.y, r.size.width, r.size.height
            cx, cy = rx + rw / 2, ry + rh / 2

            # Soft fill
            NSColor.colorWithRed_green_blue_alpha_(0.0, 0.70, 1.0, 0.18).setFill()
            outer = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(r, 10, 10)
            outer.fill()

            # Inner fill
            NSColor.colorWithRed_green_blue_alpha_(0.05, 0.65, 1.0, 0.28).setFill()
            inner_r = NSMakeRect(rx + 2, ry + 2, rw - 4, rh - 4)
            inner = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(inner_r, 8, 8)
            inner.fill()

            # Bright border
            NSColor.colorWithRed_green_blue_alpha_(0.0, 0.92, 1.0, 0.88).setStroke()
            inner.setLineWidth_(1.5)
            inner.stroke()

            # Dwell countdown arc — yellow → green, fills clockwise from top
            pct = getattr(self, '_dwell_pct', 0.0)
            if pct > 0.01:
                r_ch = 1.0 * (1.0 - pct)          # red: 1→0
                g_ch = 0.7 + 0.3 * pct             # green: 0.7→1.0
                NSColor.colorWithRed_green_blue_alpha_(r_ch, g_ch, 0.0, 0.92).setStroke()
                arc_radius = max(5.0, min(rw, rh) / 2 - 3)
                arc = NSBezierPath.bezierPath()
                try:
                    arc.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(
                        (cx, cy), arc_radius, 90.0, 90.0 - pct * 360.0, True
                    )
                    arc.setLineWidth_(3.5)
                    arc.stroke()
                except Exception:
                    pass

    _OBJC_OK = True
except Exception as _e:
    _OBJC_OK = False
    print(f"[gaze_overlay] PyObjC unavailable: {_e}")

# ── Element rect cache ─────────────────────────────────────────────────────────
_FALLBACK_W = 180
_FALLBACK_H = 90
_AX_POLL    = 0.10   # seconds between Accessibility API calls


class _RectCache:
    def __init__(self):
        self._t   = 0.0
        self._pos = None
        self._hit = None

    def get(self, x: float, y: float):
        now = time.monotonic()
        moved = self._pos is None or abs(x - self._pos[0]) > 50 or abs(y - self._pos[1]) > 50
        if now - self._t < _AX_POLL and not moved:
            return self._hit
        self._t   = now
        self._pos = (x, y)
        self._hit = _ax_rect(x, y)
        return self._hit


def _ax_rect(x: float, y: float):
    """Return (ex, ey, ew, eh) of the AX element at (x,y), or None."""
    try:
        import ctypes
        from ApplicationServices import (
            AXUIElementCreateSystemWide,
            AXUIElementCopyElementAtPosition,
            AXUIElementCopyAttributeValue,
            kAXPositionAttribute, kAXSizeAttribute,
        )

        _lib = ctypes.cdll.LoadLibrary(
            '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices'
        )
        _lib.AXValueGetValue.restype  = ctypes.c_bool
        _lib.AXValueGetValue.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]

        class _CGPt(ctypes.Structure):
            _fields_ = [('x', ctypes.c_double), ('y', ctypes.c_double)]
        class _CGSz(ctypes.Structure):
            _fields_ = [('width', ctypes.c_double), ('height', ctypes.c_double)]

        sys_el = AXUIElementCreateSystemWide()
        err, elem = AXUIElementCopyElementAtPosition(sys_el, float(x), float(y), None)
        if err != 0 or elem is None:
            return None
        e1, pv = AXUIElementCopyAttributeValue(elem, kAXPositionAttribute, None)
        e2, sv = AXUIElementCopyAttributeValue(elem, kAXSizeAttribute, None)
        if e1 or e2 or pv is None or sv is None:
            return None

        # Unwrap AXValueRef → CGPoint / CGSize via objc_object id
        pt, sz = _CGPt(), _CGSz()
        # AXValueRef is a CFTypeRef; its raw pointer lives at id(obj) on CPython
        ok1 = _lib.AXValueGetValue(id(pv),  1, ctypes.byref(pt))
        ok2 = _lib.AXValueGetValue(id(sv),  2, ctypes.byref(sz))
        if not (ok1 and ok2):
            return None
        w, h = sz.width, sz.height
        if not (4 < w < 3000 and 4 < h < 2000):
            return None
        return pt.x, pt.y, w, h
    except Exception:
        return None


# ── Main overlay class ─────────────────────────────────────────────────────────

class GazeOverlay:
    def __init__(self):
        self._window  = None
        self._view    = None
        self._visible = False
        self._screen_h = 0
        self._cache   = _RectCache()

        if not _OBJC_OK:
            return
        try:
            self._screen_h = NSScreen.mainScreen().frame().size.height
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

            # Create view ONCE — reused for lifetime of overlay
            view = _GlowView.alloc().initWithFrame_(rect)
            win.setContentView_(view)

            self._window  = win
            self._view    = view
            print("[gaze_overlay] Overlay ready.")
        except Exception as e:
            print(f"[gaze_overlay] Init error: {e}")

    def update(self, gx: float, gy: float, dwell_pct: float = 0.0):
        """Reposition the overlay to gaze point (gx, gy) in screen coords.

        dwell_pct: 0.0–1.0 progress of dwell-to-click countdown.
        """
        if self._window is None:
            return
        rect = self._cache.get(gx, gy)
        if rect:
            ex, ey, ew, eh = rect
        else:
            ew, eh = _FALLBACK_W, _FALLBACK_H
            ex, ey = gx - ew / 2, gy - eh / 2

        # Push dwell progress to view for arc rendering
        if self._view is not None:
            self._view._dwell_pct = float(dwell_pct)

        cocoa_y = self._screen_h - ey - eh
        try:
            self._window.setFrame_display_(NSMakeRect(ex, cocoa_y, ew, eh), True)
            self._view.setNeedsDisplay_(True)
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
        """Give Cocoa 0ms to process pending draw/move events."""
        if not _OBJC_OK:
            return
        try:
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.0)
            )
        except Exception:
            pass

    def close(self):
        self.hide()
