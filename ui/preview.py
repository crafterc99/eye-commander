"""Jarvis-style HUD — draws hand skeleton + status overlay on camera frame."""

import cv2
import numpy as np
from core.hand_tracker import HAND_CONNECTIONS, FINGERTIPS, INDEX_TIP, THUMB_TIP

# Jarvis color palette
_CYAN    = (255, 220, 0)     # BGR cyan-gold
_BLUE    = (255, 160, 20)    # BGR bright blue
_GREEN   = (80,  255, 120)   # BGR green
_RED     = (60,  60,  255)   # BGR red
_WHITE   = (240, 240, 240)
_DIM     = (80,  80,  80)
_ORANGE  = (0,   160, 255)   # BGR orange
_BG      = (10,  10,  15)


def draw_frame(frame, hand_result, mode, fps, gesture, screen_pos=None, screen_w=1920, screen_h=1080, hud_state=None, cursor_source="hand"):
    if frame is None:
        return None

    out = cv2.flip(frame.copy(), 1)  # mirror like selfie
    h, w = out.shape[:2]

    # Dark vignette overlay for Jarvis feel
    _vignette(out)

    if hand_result is not None:
        fw, fh = hand_result.frame_size

        def m(pt):
            """Mirror + scale landmark to preview frame."""
            x, y = pt
            return (int((1.0 - x / fw) * w), int(y / fh * h))

        lms_m = [m(lm) for lm in hand_result.landmarks_px]

        # Draw skeleton connections
        for (a, b) in HAND_CONNECTIONS:
            pa, pb = lms_m[a], lms_m[b]
            cv2.line(out, pa, pb, _BLUE, 1, cv2.LINE_AA)

        # Glow on connections (second thicker pass, dimmer)
        for (a, b) in HAND_CONNECTIONS:
            pa, pb = lms_m[a], lms_m[b]
            cv2.line(out, pa, pb, (60, 40, 5), 4, cv2.LINE_AA)
            cv2.line(out, pa, pb, _BLUE, 1, cv2.LINE_AA)

        # Draw all landmarks
        for i, pt in enumerate(lms_m):
            color = _CYAN if i in FINGERTIPS else _BLUE
            radius = 6 if i in FINGERTIPS else 3
            cv2.circle(out, pt, radius + 2, (int(color[0]*0.3), int(color[1]*0.3), int(color[2]*0.3)), -1)
            cv2.circle(out, pt, radius, color, -1, cv2.LINE_AA)

        # Highlight index tip and thumb tip
        cv2.circle(out, lms_m[INDEX_TIP], 9, _GREEN, 2, cv2.LINE_AA)
        cv2.circle(out, lms_m[THUMB_TIP], 8, _ORANGE, 2, cv2.LINE_AA)

        # Pinch line — colour based on enter threshold
        from core.hand_tracker import WRIST, MIDDLE_MCP as _MMCP
        palm_sz = max(1.0, ((hand_result.landmarks_px[WRIST][0] - hand_result.landmarks_px[_MMCP][0])**2 +
                            (hand_result.landmarks_px[WRIST][1] - hand_result.landmarks_px[_MMCP][1])**2) ** 0.5)
        import config as _cfg
        tip_t  = hand_result.landmarks_px[THUMB_TIP]
        tip_i  = hand_result.landmarks_px[INDEX_TIP]
        pd_norm = ((tip_t[0]-tip_i[0])**2 + (tip_t[1]-tip_i[1])**2)**0.5 / palm_sz
        pinch_color = _RED if pd_norm < _cfg.PINCH_ENTER_THRESH else _DIM
        cv2.line(out, lms_m[INDEX_TIP], lms_m[THUMB_TIP], pinch_color, 1, cv2.LINE_AA)

        # Fist charge arc
        if hud_state and hud_state.get("fist_charge", 0) > 0:
            import math
            wrist_pt = lms_m[0]  # index 0 = WRIST
            charge = hud_state["fist_charge"]
            end_angle = int(-90 + charge * 360)
            cv2.ellipse(out, wrist_pt, (22, 22), 0, -90, end_angle, _ORANGE, 3, cv2.LINE_AA)

    # --- Top status bar ---
    cv2.rectangle(out, (0, 0), (w, 36), (5, 5, 10), -1)
    _scanline(out, 35)
    dict_status = hud_state.get("dict_status", "idle") if hud_state else "idle"
    active_app  = hud_state.get("active_app", "") if hud_state else ""
    _cs = hud_state.get("cursor_source", cursor_source) if hud_state else cursor_source
    mode_color  = (_GREEN  if mode == "tracking"
                   else _RED    if mode == "paused"
                   else _CYAN   if mode in ("active", "dictating")
                   else _ORANGE if mode == "composing"
                   else _WHITE)
    src_label = "EYES" if _cs == "gaze" else "HAND"
    src_color  = _CYAN if _cs == "gaze" else _GREEN
    app_tag = f"  [{active_app}]" if active_app else ""
    cv2.putText(out, f"JARVIS  |  {mode.upper()}  |  {fps:.0f} FPS  |  {gesture}{app_tag}",
                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.52, mode_color, 1, cv2.LINE_AA)
    # Cursor source badge (top-right)
    cv2.putText(out, f"CURSOR: {src_label}", (w - 115, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, src_color, 1, cv2.LINE_AA)

    # --- Compose buffer overlay ---
    if hud_state:
        compose_text = hud_state.get("compose_text", "")
        partial_text = hud_state.get("partial_text", "")
        if compose_text or partial_text or dict_status in ("active", "composing"):
            _draw_dictation_overlay(out, w, h, compose_text, partial_text, dict_status)

    # --- Gaze minimap ---
    if screen_pos is not None:
        _draw_minimap(out, screen_pos, screen_w, screen_h, w, h)

    # --- Bottom hint bar ---
    cv2.rectangle(out, (0, h - 76), (w, h), (5, 5, 10), -1)
    _scanline(out, h - 76)
    hints = [
        ("INDEX POINT", "→ move cursor",  _CYAN),
        ("PINCH",       "→ click",        _GREEN),
        ("PINCH HOLD",  "→ drag",         _ORANGE),
        ("PEACE SPREAD","→ right click",  _BLUE),
        ("3 FINGERS",   "→ scroll",       _WHITE),
        ("FIST 0.45s",  "→ pause",        _RED),
    ]
    x = 8
    for label, action, color in hints:
        cv2.putText(out, label, (x, h - 52), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
        cv2.putText(out, action, (x, h - 34), cv2.FONT_HERSHEY_SIMPLEX, 0.35, _DIM, 1, cv2.LINE_AA)
        x += 110

    cv2.putText(out, "SAY: 'type'/'dictate'  |  'eye mode'/'hand mode'  |  'calibrate gaze'  |  'click' 'copy' 'quit'",
                (8, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 200, 120), 1, cv2.LINE_AA)

    return out


def _vignette(img):
    h, w = img.shape[:2]
    # Darken corners for cinematic look
    mask = np.zeros((h, w), dtype=np.float32)
    cx, cy = w // 2, h // 2
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            d = ((x - cx)**2 / (cx**2) + (y - cy)**2 / (cy**2)) ** 0.5
            mask[y, y:y+4] = min(1.0, d * 0.6)
    # Fast approximation: just darken border strip
    border = 40
    img[:border, :] = (img[:border, :] * 0.4).astype(np.uint8)
    img[-border:, :] = (img[-border:, :] * 0.4).astype(np.uint8)
    img[:, :border] = (img[:, :border] * 0.4).astype(np.uint8)
    img[:, -border:] = (img[:, -border:] * 0.4).astype(np.uint8)


def _scanline(img, y):
    """Draw a subtle cyan scan line."""
    cv2.line(img, (0, y), (img.shape[1], y), (80, 60, 0), 1)


def _draw_dictation_overlay(out, w, h, compose_text, partial_text, status):
    """Draw a translucent compose/dictation box in the lower-centre of the frame."""
    box_h  = 80
    box_w  = w - 40
    bx, by = 20, h - 76 - box_h - 8
    # Semi-transparent background
    overlay = out.copy()
    cv2.rectangle(overlay, (bx, by), (bx + box_w, by + box_h), (8, 8, 20), -1)
    cv2.addWeighted(overlay, 0.75, out, 0.25, 0, out)
    # Border colour by status
    border_col = _ORANGE if status == "composing" else _CYAN
    cv2.rectangle(out, (bx, by), (bx + box_w, by + box_h), border_col, 1)

    # Label
    label = "COMPOSE — say 'submit' or 'cancel'" if status == "composing" else "DICTATING"
    cv2.putText(out, label, (bx + 8, by + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, border_col, 1, cv2.LINE_AA)

    # Compose text (confirmed)
    display = compose_text[-80:] if len(compose_text) > 80 else compose_text
    cv2.putText(out, display, (bx + 8, by + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, _WHITE, 1, cv2.LINE_AA)

    # Partial (live grey)
    if partial_text:
        pdisp = partial_text[:60]
        cv2.putText(out, pdisp, (bx + 8, by + 62),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, _DIM, 1, cv2.LINE_AA)


def _draw_minimap(frame, screen_pos, sw, sh, fw, fh):
    mw, mh = 130, 74
    mx0, my0 = fw - mw - 8, fh - mh - 84
    # Background
    cv2.rectangle(frame, (mx0 - 1, my0 - 1), (mx0 + mw + 1, my0 + mh + 1), _BLUE, 1)
    cv2.rectangle(frame, (mx0, my0), (mx0 + mw, my0 + mh), (8, 8, 15), -1)
    # Grid lines
    for gx in [mx0 + mw//3, mx0 + 2*mw//3]:
        cv2.line(frame, (gx, my0), (gx, my0 + mh), (30, 25, 5), 1)
    for gy in [my0 + mh//2]:
        cv2.line(frame, (mx0, gy), (mx0 + mw, gy), (30, 25, 5), 1)
    # Gaze dot
    gx = int(mx0 + screen_pos[0] / sw * mw)
    gy = int(my0 + screen_pos[1] / sh * mh)
    gx = max(mx0 + 3, min(mx0 + mw - 3, gx))
    gy = max(my0 + 3, min(my0 + mh - 3, gy))
    cv2.circle(frame, (gx, gy), 5, _CYAN, -1, cv2.LINE_AA)
    cv2.circle(frame, (gx, gy), 8, _CYAN, 1, cv2.LINE_AA)
    cv2.putText(frame, "CURSOR", (mx0 + 4, my0 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.3, _BLUE, 1, cv2.LINE_AA)
