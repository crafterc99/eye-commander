# Tunable thresholds and configuration for eye-commander

# --- Blink Detection ---
EAR_THRESHOLD = 0.20          # Eye Aspect Ratio below this = eye closed
EAR_CONSEC_FRAMES = 3         # Consecutive frames below threshold to confirm blink
BLINK_COOLDOWN_MS = 500       # Minimum ms between blink-triggered clicks

# --- Gaze Smoothing ---
GAZE_EMA_ALPHA = 0.3          # EMA weight for new sample (lower = smoother, more lag)
GAZE_DEAD_ZONE_PX = 5         # Min pixel delta before cursor moves

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
CAMERA_FPS = 30

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
