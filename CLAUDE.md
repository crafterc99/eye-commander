# eye-commander — Claude Code Project Instructions

## Project
Hand + eye tracking macOS controller. Stack: Python 3.9, MediaPipe, dlib/GazeTracking, OpenCV, PyAudio, pynput, OpenAI Whisper, Wispr Flow WebSocket, PyObjC.

## Key Files
- `main.py` — main loop (camera → hand → gaze → gesture → cursor → voice → HUD)
- `config.py` — all tuning constants (loads `.env` via dotenv)
- `core/hand_tracker.py` — MediaPipe hands + LandmarkSmoother
- `core/hand_cursor.py` — two-stage velocity-blended cursor
- `core/gesture_detector.py` — hysteresis state machines (pinch/fist/peace/scroll)
- `core/gaze_cursor.py` — GazeTracking background thread + auto-calibration
- `ui/gaze_overlay.py` — transparent PyObjC NSWindow gaze highlight
- `ui/preview.py` — Jarvis HUD (OpenCV overlay)
- `voice/dictation.py` — DictationManager (Wispr Flow streaming → Whisper fallback)
- `voice/wispr_dictation.py` — Wispr Flow WebSocket engine
- `voice/commands.py` — CommandDispatcher (type/submit/cancel/dictate)
- `.env` — OPENAI_API_KEY, WISPR_API_KEY (never committed)

## Run
```bash
zsh ~/Desktop/run-eye-commander.sh
```

## Dev Rules
- Virtual env: `.venv/` — always `source .venv/bin/activate`
- pip: always use `--cache ./.npm-cache` flag
- After significant changes: commit + push to GitHub
- No `GAZE_EMA_ALPHA` / `GAZE_DEAD_ZONE_PX` removal — `gaze_estimator.py` uses them

## Superpowers Skills Active
Skills are available via the `Skill` tool. Invoke relevant skills before acting:

| Trigger | Skill |
|---|---|
| Building any feature | `brainstorming` first |
| Multi-step work | `writing-plans` → `executing-plans` |
| Any bug/unexpected behavior | `systematic-debugging` |
| Implementing feature/fix | `test-driven-development` |
| About to say "done" | `verification-before-completion` |
| 2+ independent tasks | `dispatching-parallel-agents` |
| Finishing a branch | `finishing-a-development-branch` |
