"""Head pose estimation via cv2.solvePnP → Euler angles + gesture state machine."""

import time
import numpy as np
import cv2
import config


_MODEL_3D = np.array(config.HEAD_POSE_3D_MODEL, dtype=np.float64)


class HeadPose:
    def __init__(self, callback):
        """
        callback(gesture): gesture is 'nod', 'shake', 'tilt_left', 'tilt_right'
        """
        self._callback = callback
        self._last_pitch = None
        self._last_yaw = None
        self._last_gesture_time = 0.0
        self._nod_peak = None
        self._shake_peak = None

    def update(self, face_result):
        pts_2d = np.array(face_result.head_pts_2d, dtype=np.float64)
        fw, fh = face_result.frame_size
        focal = fw
        cam_matrix = np.array([
            [focal, 0, fw / 2],
            [0, focal, fh / 2],
            [0, 0, 1],
        ], dtype=np.float64)
        dist_coeffs = np.zeros((4, 1))

        success, rvec, tvec = cv2.solvePnP(
            _MODEL_3D, pts_2d, cam_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        if not success:
            return None

        rmat, _ = cv2.Rodrigues(rvec)
        sy = np.sqrt(rmat[0, 0]**2 + rmat[1, 0]**2)
        singular = sy < 1e-6

        if not singular:
            pitch = np.degrees(np.arctan2(-rmat[2, 1], rmat[2, 2]))
            yaw   = np.degrees(np.arctan2(rmat[2, 0], sy))
            roll  = np.degrees(np.arctan2(-rmat[1, 0], rmat[0, 0]))
        else:
            pitch = np.degrees(np.arctan2(-rmat[1, 2], rmat[1, 1]))
            yaw   = np.degrees(np.arctan2(rmat[2, 0], sy))
            roll  = 0.0

        self._detect_gestures(pitch, yaw, roll)
        self._last_pitch = pitch
        self._last_yaw = yaw
        return pitch, yaw, roll

    def _detect_gestures(self, pitch, yaw, roll):
        now = time.time()
        debounce = config.HEAD_GESTURE_DEBOUNCE_MS / 1000.0

        if now - self._last_gesture_time < debounce:
            return

        # Tilt gestures (immediate threshold)
        if roll > config.TILT_ROLL_THRESHOLD:
            self._fire("tilt_left")
            return
        if roll < -config.TILT_ROLL_THRESHOLD:
            self._fire("tilt_right")
            return

        # Nod: pitch crosses zero in a meaningful arc
        if self._last_pitch is not None:
            d_pitch = pitch - self._last_pitch
            if abs(d_pitch) > config.NOD_PITCH_THRESHOLD:
                self._fire("nod")
                return

        # Shake: yaw crosses midpoint meaningfully
        if self._last_yaw is not None:
            d_yaw = yaw - self._last_yaw
            if abs(d_yaw) > config.SHAKE_YAW_THRESHOLD:
                self._fire("shake")
                return

    def _fire(self, gesture):
        self._last_gesture_time = time.time()
        self._callback(gesture)
