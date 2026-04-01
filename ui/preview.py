"""Camera preview window with eye tracking overlay drawn on the live frame."""

import cv2
import numpy as np


def draw_tracking(frame, face_result, ear_l, ear_r, mode, fps, last_event, gaze_screen=None, screen_w=1920, screen_h=1080):
    """Draw iris dots, EAR bars, gaze info and status onto frame. Returns annotated frame."""
    if frame is None:
        return None

    out = frame.copy()
    h, w = out.shape[:2]

    # --- Mirror so it feels like a selfie ---
    out = cv2.flip(out, 1)

    if face_result is not None:
        fw, fh = face_result.frame_size

        def px_mirror(pt):
            """Flip x to match mirrored frame."""
            x, y = pt
            return (int(w - x * w / fw), int(y * fh / fh * h / fh))

        # Draw iris circles
        rx, ry = face_result.iris_right
        lx, ly = face_result.iris_left
        mrx = int(w - rx * w / fw)
        mry = int(ry * h / fh)
        mlx = int(w - lx * w / fw)
        mly = int(ly * h / fh)

        r_color = (0, 255, 100) if ear_r > 0.20 else (0, 80, 255)
        l_color = (0, 255, 100) if ear_l > 0.20 else (0, 80, 255)
        cv2.circle(out, (mrx, mry), 8, r_color, 2)
        cv2.circle(out, (mrx, mry), 2, (255, 255, 255), -1)
        cv2.circle(out, (mlx, mly), 8, l_color, 2)
        cv2.circle(out, (mlx, mly), 2, (255, 255, 255), -1)

        # EAR bars on the sides
        _draw_ear_bar(out, ear_r, x=20, y=60, label="R")
        _draw_ear_bar(out, ear_l, x=w - 50, y=60, label="L")

        # Draw key face landmarks (nose tip, mouth corners)
        for idx in [1, 61, 291]:
            if idx < len(face_result.landmarks_px):
                lm = face_result.landmarks_px[idx]
                mx = int(w - lm[0] * w / fw)
                my = int(lm[1] * h / fh)
                cv2.circle(out, (mx, my), 3, (100, 200, 255), -1)

    # --- Gaze mini-map (bottom-right corner) ---
    if gaze_screen is not None:
        _draw_minimap(out, gaze_screen, screen_w, screen_h, w, h)

    # --- HUD text ---
    blink_hint = "Blink L=click  R=right-click  Both=dbl"
    gesture_hint = "Nod=Enter  Shake=Esc  Tilt=Scroll"
    voice_hint = "Say: 'type hello' | 'click' | 'scroll up' | 'quit'"

    cv2.rectangle(out, (0, h - 90), (w, h), (0, 0, 0), -1)
    cv2.putText(out, blink_hint,  (10, h - 68), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 255, 180), 1)
    cv2.putText(out, gesture_hint,(10, h - 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 220, 255), 1)
    cv2.putText(out, voice_hint,  (10, h - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 220, 160), 1)

    # Status bar top
    cv2.rectangle(out, (0, 0), (w, 32), (20, 20, 20), -1)
    status = f"  mode={mode}   fps={fps:.0f}   EAR L={ear_l:.2f} R={ear_r:.2f}   {last_event}"
    cv2.putText(out, status, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    return out


def _draw_ear_bar(frame, ear, x, y, label):
    bar_h = 80
    filled = int(bar_h * min(ear / 0.4, 1.0))
    color = (0, 200, 80) if ear > 0.20 else (0, 60, 200)
    cv2.rectangle(frame, (x, y), (x + 18, y + bar_h), (60, 60, 60), -1)
    cv2.rectangle(frame, (x, y + bar_h - filled), (x + 18, y + bar_h), color, -1)
    cv2.putText(frame, label, (x + 2, y + bar_h + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    cv2.putText(frame, f"{ear:.2f}", (x - 4, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)


def _draw_minimap(frame, gaze_screen, sw, sh, fw, fh):
    """Small screen map in bottom-right showing gaze dot."""
    mw, mh = 120, 68
    mx0, my0 = fw - mw - 10, fh - mh - 100
    cv2.rectangle(frame, (mx0, my0), (mx0 + mw, my0 + mh), (50, 50, 50), -1)
    cv2.rectangle(frame, (mx0, my0), (mx0 + mw, my0 + mh), (120, 120, 120), 1)
    # gaze dot
    gx = int(mx0 + gaze_screen[0] / sw * mw)
    gy = int(my0 + gaze_screen[1] / sh * mh)
    gx = max(mx0 + 4, min(mx0 + mw - 4, gx))
    gy = max(my0 + 4, min(my0 + mh - 4, gy))
    cv2.circle(frame, (gx, gy), 5, (0, 220, 255), -1)
    cv2.putText(frame, "gaze", (mx0 + 4, my0 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)
