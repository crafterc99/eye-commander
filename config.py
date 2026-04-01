# Tunable thresholds and configuration for eye-commander
import os
from dotenv import load_dotenv
load_dotenv()  # loads .env if present

# --- Blink Detection ---
EAR_THRESHOLD = 0.20          # Eye Aspect Ratio below this = eye closed
EAR_CONSEC_FRAMES = 3         # Consecutive frames below threshold to confirm blink
BLINK_COOLDOWN_MS = 500       # Minimum ms between blink-triggered clicks

# --- Legacy gaze smoother (used by gaze_estimator.py) ---
GAZE_EMA_ALPHA    = 0.15     # heavy smoothing for iris-based gaze
GAZE_DEAD_ZONE_PX = 8        # px dead zone for iris gaze

# --- GazeTracking (dlib) cursor ---
GAZE_CURSOR_ENABLED = True   # set False to disable eye-gaze mouse movement

# --- Landmark Pre-smoothing ---
LANDMARK_EMA_ALPHA = 0.60     # Per-landmark EMA before cursor/gesture logic

# --- Two-stage velocity-blended cursor ---
CURSOR_FAST_ALPHA  = 0.45
CURSOR_SLOW_ALPHA  = 0.18
CURSOR_VELOCITY_BLEND_SCALE = 80.0
CURSOR_VELOCITY_BLEND_MIN   = 0.0
CURSOR_VELOCITY_BLEND_MAX   = 0.85
CURSOR_DEAD_ZONE_NORM = 0.0025   # Normalised ~3.6px on 1920w

# --- Hand canvas (virtual region that maps to full screen) ---
HAND_CANVAS_LEFT   = 0.15
HAND_CANVAS_RIGHT  = 0.85
HAND_CANVAS_TOP    = 0.10
HAND_CANVAS_BOTTOM = 0.85

# --- Pinch / drag ---
PINCH_ENTER_THRESH  = 0.28
PINCH_EXIT_THRESH   = 0.42
PINCH_COOLDOWN_SECS = 0.40
DRAG_HOLD_SECS      = 0.35

# --- Fist pause ---
FIST_ENTER_HOLD_SECS  = 0.45
FIST_EXIT_OPEN_FRAMES = 8

# --- Peace right-click ---
PEACE_SPREAD_THRESH = 0.30
PEACE_HOLD_FRAMES   = 6

# --- Continuous scroll ---
SCROLL_VELOCITY_SCALE = 18.0
SCROLL_MIN_VELOCITY   = 0.004
SCROLL_SMOOTHING      = 0.35

# --- Calibration ---
CALIBRATION_DWELL_SECS = 3.0  # Seconds to look at each calibration dot
CALIBRATION_SAMPLES = 30      # Number of iris samples to collect per dot
CALIBRATION_FILE = "calibration.json"

# --- Head Pose Gestures ---
HEAD_GESTURE_DEBOUNCE_MS = 300   # Min ms between gesture triggers
NOD_PITCH_THRESHOLD = 15.0       # Degrees pitch change for nod detection
SHAKE_YAW_THRESHOLD = 25.0       # Degrees yaw change for shake detection
TILT_ROLL_THRESHOLD = 20.0       # Degrees roll for tilt detection

# --- Camera ---
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 60          # Request 60fps (camera will cap at its max)

# --- Voice ---
VOSK_MODEL_PATH = "models/vosk"
VOSK_SAMPLE_RATE = 16000
VOSK_CHUNK_SIZE = 4096

# --- MediaPipe ---
MEDIAPIPE_MODEL_PATH = "models/face_landmarker.task"
MEDIAPIPE_MIN_DETECTION_CONFIDENCE = 0.5
MEDIAPIPE_MIN_TRACKING_CONFIDENCE = 0.5

# --- Iris landmark indices ---
IRIS_RIGHT_CENTER = 468
IRIS_LEFT_CENTER = 473

# --- EAR landmark indices ---
EAR_RIGHT_POINTS = [33, 160, 158, 133, 153, 144]
EAR_LEFT_POINTS = [362, 385, 387, 263, 373, 380]

# --- Head pose anchor landmarks ---
HEAD_POSE_POINTS = [1, 152, 33, 263, 61, 291]  # nose, chin, eye inner corners, mouth corners

# --- 3D model points for solvePnP (normalized face model) ---
HEAD_POSE_3D_MODEL = [
    [0.0,   0.0,    0.0],    # Nose tip (1)
    [0.0,  -330.0, -65.0],   # Chin (152)
    [-225.0, 170.0,-135.0],  # Left eye inner corner (33)
    [225.0,  170.0,-135.0],  # Right eye inner corner (263)
    [-150.0,-150.0,-125.0],  # Left mouth corner (61)
    [150.0, -150.0,-125.0],  # Right mouth corner (291)
]

# --- Scroll ---
SCROLL_TICKS_DEFAULT = 3

# --- Dictation (Whisper) ---
DICTATION_VAD_ENERGY_THRESH = 500   # RMS level to consider as speech (tune per mic)

# --- Gaze dwell-to-click (gaze cursor mode only) ---
GAZE_DWELL_SECS      = 1.3   # seconds of stable gaze before click fires
GAZE_DWELL_RADIUS_PX = 60    # gaze can wander this many px and still be "stable"

# --- Gesture palm height gate ---
# Palm Y is 0=top, 1=bottom in frame. Resting hand on desk is near bottom.
GESTURE_MIN_PALM_Y_NORM = 0.72   # Y > this → suppress all gestures (hand is resting)

# --- Pinch anti-tremor ---
PINCH_MIN_HOLD_SECS = 0.10   # must hold pinch ≥ 100ms to register as click
