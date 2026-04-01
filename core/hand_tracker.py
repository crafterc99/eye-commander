"""MediaPipe Hands — 21-landmark hand tracker."""

import mediapipe as mp
import numpy as np

_mp_hands = mp.solutions.hands
HAND_CONNECTIONS = _mp_hands.HAND_CONNECTIONS

# Landmark indices
WRIST       = 0
THUMB_CMC   = 1;  THUMB_MCP  = 2;  THUMB_IP  = 3;  THUMB_TIP  = 4
INDEX_MCP   = 5;  INDEX_PIP  = 6;  INDEX_DIP = 7;  INDEX_TIP  = 8
MIDDLE_MCP  = 9;  MIDDLE_PIP = 10; MIDDLE_DIP= 11; MIDDLE_TIP = 12
RING_MCP    = 13; RING_PIP   = 14; RING_DIP  = 15; RING_TIP   = 16
PINKY_MCP   = 17; PINKY_PIP  = 18; PINKY_DIP = 19; PINKY_TIP  = 20

FINGERTIPS  = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
FINGER_MCPS = [THUMB_MCP, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]


class HandTracker:
    def __init__(self):
        self._hands = _mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
        )

    def process(self, frame_bgr):
        """Returns HandResult or None."""
        rgb = frame_bgr[:, :, ::-1].copy()
        result = self._hands.process(rgb)
        if not result.multi_hand_landmarks:
            return None
        h, w = frame_bgr.shape[:2]
        lms = result.multi_hand_landmarks[0]
        landmarks_px = [(lm.x * w, lm.y * h) for lm in lms.landmark]
        return HandResult(landmarks_px=landmarks_px, frame_size=(w, h))

    def close(self):
        self._hands.close()


class HandResult:
    def __init__(self, landmarks_px, frame_size):
        self.landmarks_px = landmarks_px
        self.frame_size = frame_size

    def tip(self, idx):
        return self.landmarks_px[idx]

    def palm_center(self):
        pts = [self.landmarks_px[i] for i in [WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    def palm_size(self):
        """Distance from wrist to middle MCP — normalisation factor."""
        w = self.landmarks_px[WRIST]
        m = self.landmarks_px[MIDDLE_MCP]
        return max(1.0, ((w[0]-m[0])**2 + (w[1]-m[1])**2) ** 0.5)

    def finger_extended(self, finger_idx):
        """True if finger tip is above its MCP (y decreases upward in image)."""
        tip = self.landmarks_px[FINGERTIPS[finger_idx]]
        pip = self.landmarks_px[FINGER_MCPS[finger_idx]]
        return tip[1] < pip[1]

    def fingers_up(self):
        """Returns list of bools [thumb, index, middle, ring, pinky]."""
        return [self.finger_extended(i) for i in range(5)]
