"""MediaPipe Face Landmarker wrapper — extracts iris, EAR landmarks, and head pose points."""

import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
import config


class FaceTracker:
    def __init__(self):
        base_options = mp_python.BaseOptions(model_asset_path=config.MEDIAPIPE_MODEL_PATH)
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=1,
            min_face_detection_confidence=config.MEDIAPIPE_MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.MEDIAPIPE_MIN_TRACKING_CONFIDENCE,
        )
        self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)

    def process(self, frame_bgr):
        """
        Process a BGR frame and return a FaceResult or None.
        FaceResult has:
            .landmarks_px  - all 478 landmarks as (x, y) pixel coords
            .iris_right    - (x, y) of right iris center in pixels
            .iris_left     - (x, y) of left iris center in pixels
            .ear_right_pts - 6 (x, y) points for right EAR
            .ear_left_pts  - 6 (x, y) points for left EAR
            .head_pts_2d   - 6 (x, y) anchor points for solvePnP
        """
        import mediapipe as mp
        h, w = frame_bgr.shape[:2]
        rgb = frame_bgr[:, :, ::-1].copy()
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect(mp_image)
        if not result.face_landmarks:
            return None
        lms = result.face_landmarks[0]

        def lm_px(idx):
            lm = lms[idx]
            return (lm.x * w, lm.y * h)

        landmarks_px = [lm_px(i) for i in range(len(lms))]

        iris_right = lm_px(config.IRIS_RIGHT_CENTER)
        iris_left = lm_px(config.IRIS_LEFT_CENTER)
        ear_right_pts = [lm_px(i) for i in config.EAR_RIGHT_POINTS]
        ear_left_pts = [lm_px(i) for i in config.EAR_LEFT_POINTS]
        head_pts_2d = [lm_px(i) for i in config.HEAD_POSE_POINTS]

        return FaceResult(
            landmarks_px=landmarks_px,
            iris_right=iris_right,
            iris_left=iris_left,
            ear_right_pts=ear_right_pts,
            ear_left_pts=ear_left_pts,
            head_pts_2d=head_pts_2d,
            frame_size=(w, h),
        )

    def close(self):
        self._landmarker.close()


class FaceResult:
    def __init__(self, landmarks_px, iris_right, iris_left,
                 ear_right_pts, ear_left_pts, head_pts_2d, frame_size):
        self.landmarks_px = landmarks_px
        self.iris_right = iris_right
        self.iris_left = iris_left
        self.ear_right_pts = ear_right_pts
        self.ear_left_pts = ear_left_pts
        self.head_pts_2d = head_pts_2d
        self.frame_size = frame_size
