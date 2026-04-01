#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "  eye-commander setup"
echo "=================================================="

# 1. Create virtual environment
if [ ! -d ".venv" ]; then
  echo "[1/4] Creating Python virtual environment..."
  python3 -m venv .venv
else
  echo "[1/4] Virtual environment already exists, skipping."
fi

source .venv/bin/activate

# 2. Install dependencies
echo "[2/4] Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install --cache-dir ./.pip-cache -r requirements.txt

# 3. Download Vosk model
VOSK_MODEL_DIR="models/vosk"
if [ -d "$VOSK_MODEL_DIR" ] && [ "$(ls -A $VOSK_MODEL_DIR 2>/dev/null)" ]; then
  echo "[3/4] Vosk model already present, skipping download."
else
  echo "[3/4] Downloading Vosk small English model (~50 MB)..."
  mkdir -p "$VOSK_MODEL_DIR"
  VOSK_URL="https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
  VOSK_ZIP="/tmp/vosk-model.zip"
  curl -L -o "$VOSK_ZIP" "$VOSK_URL"
  unzip -q "$VOSK_ZIP" -d /tmp/vosk-extract
  mv /tmp/vosk-extract/vosk-model-small-en-us-0.15/* "$VOSK_MODEL_DIR/"
  rm -rf "$VOSK_ZIP" /tmp/vosk-extract
  echo "  Vosk model installed at $VOSK_MODEL_DIR"
fi

# 4. Download MediaPipe Face Landmarker task
MP_MODEL="models/face_landmarker.task"
if [ -f "$MP_MODEL" ]; then
  echo "[4/4] MediaPipe model already present, skipping download."
else
  echo "[4/4] Downloading MediaPipe Face Landmarker model (~30 MB)..."
  mkdir -p models
  curl -L -o "$MP_MODEL" \
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
  echo "  MediaPipe model installed at $MP_MODEL"
fi

echo ""
echo "=================================================="
echo "  Setup complete!"
echo ""
echo "  IMPORTANT — macOS Permissions Required:"
echo ""
echo "  1. Camera: will be prompted on first run."
echo "  2. Microphone: will be prompted on first run."
echo "  3. Accessibility (REQUIRED for mouse/keyboard control):"
echo "     Open: System Settings → Privacy & Security → Accessibility"
echo "     Add your terminal app (Terminal, iTerm2, etc.) and enable it."
echo ""
echo "  To run:"
echo "    source .venv/bin/activate"
echo "    python main.py"
echo "=================================================="
