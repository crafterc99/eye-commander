"""Dictation manager — uses Wispr Flow streaming if WISPR_API_KEY is set,
falls back to batch OpenAI Whisper otherwise.

Modes
-----
Immediate  ("dictate")  — each transcribed segment is typed instantly
Compose    ("type")     — text accumulates silently; "submit" types + Enter,
                          "cancel" clears

Both modes show live partial text in the HUD via on_partial callback.
"""

import os
import io
import json
import queue
import struct
import threading
import time
import wave
import pyaudio
import config

# Lazy imports for optional backends
_openai_available = False
try:
    from openai import OpenAI
    _openai_available = True
except ImportError:
    pass

# --- VAD constants (fallback Whisper engine) ---
_RATE              = 16000
_CHANNELS          = 1
_FORMAT            = pyaudio.paInt16
_CHUNK             = 1024
_SILENCE_MS        = 700
_SILENCE_CHUNKS    = int(_SILENCE_MS / (_CHUNK / _RATE * 1000))
_MIN_SPEECH_CHUNKS = 5


class DictationManager:
    """Top-level manager: picks Wispr or Whisper, handles compose state."""

    def __init__(self, on_partial=None, on_final=None, on_status=None):
        self._on_partial = on_partial or (lambda t: None)
        self._on_final   = on_final   or (lambda t: None)
        self._on_status  = on_status  or (lambda s: None)

        # Compose buffer
        self._compose_mode = False
        self._compose_text = ""
        self._compose_lock = threading.Lock()

        # Will be set in start()
        self._engine = None

    # --- Lifecycle ---

    def start(self):
        # Try Wispr first
        wispr_key = os.environ.get("WISPR_API_KEY", "")
        if wispr_key and not wispr_key.startswith("your"):
            from voice.wispr_dictation import WisprDictationEngine
            engine = WisprDictationEngine(
                on_partial=self._handle_partial,
                on_final=self._handle_final,
                on_status=self._on_status,
            )
            if engine.start():
                self._engine = engine
                print("[dictation] Using Wispr Flow streaming.")
                return

        # Fall back to batch Whisper
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key and not api_key.startswith("sk-your"):
            engine = _WhisperEngine(
                on_partial=self._handle_partial,
                on_final=self._handle_final,
                on_status=self._on_status,
            )
            engine.start()
            self._engine = engine
            print("[dictation] Using OpenAI Whisper (batch).")
            return

        print("[dictation] No API keys found — dictation disabled.")

    def stop(self):
        if self._engine:
            self._engine.stop()

    # --- Mode control ---

    @property
    def active(self):
        return self._engine.active if self._engine else False

    @property
    def compose_mode(self):
        return self._compose_mode

    @property
    def compose_text(self):
        with self._compose_lock:
            return self._compose_text

    def begin_immediate(self):
        """Dictate and type each sentence as it's recognised."""
        with self._compose_lock:
            self._compose_mode = False
            self._compose_text = ""
        if self._engine:
            self._engine.begin()
        self._on_status("active")

    def begin_compose(self):
        """Accumulate into compose buffer; nothing typed until submit()."""
        with self._compose_lock:
            self._compose_mode = True
            self._compose_text = ""
        if self._engine:
            self._engine.begin()
        self._on_status("composing")

    def end(self):
        with self._compose_lock:
            self._compose_mode = False
            self._compose_text = ""
        if self._engine:
            self._engine.end()
        self._on_status("idle")

    def submit(self) -> str:
        """Type compose_text + Enter. Returns the typed text."""
        with self._compose_lock:
            text = self._compose_text.strip()
            self._compose_text = ""
            self._compose_mode = False
        if self._engine:
            self._engine.end()
        if text:
            _type_text(text)
            _press_enter()
        self._on_status("idle")
        return text

    def cancel(self):
        """Discard compose buffer."""
        with self._compose_lock:
            self._compose_text = ""
            self._compose_mode = False
        if self._engine:
            self._engine.end()
        self._on_status("idle")
        print("[dictation] Cancelled.")

    # --- Internal callbacks ---

    def _handle_partial(self, text: str):
        self._on_partial(text)

    def _handle_final(self, text: str):
        # Check if final text is a control word
        cmd = text.strip().lower().rstrip(".,!?")
        if cmd in ("submit", "send", "enter"):
            self.submit()
            return
        if cmd in ("cancel", "nevermind", "never mind", "clear"):
            self.cancel()
            return
        if cmd in ("stop", "stop dictating", "stop dictation"):
            self.end()
            return

        with self._compose_lock:
            mode = self._compose_mode
            if mode:
                sep = " " if self._compose_text else ""
                self._compose_text += sep + text

        if not mode:
            # Immediate mode — type now
            _type_text(text + " ")
        else:
            # Let caller read compose_text via property for HUD
            pass

        self._on_final(text)


# ---------------------------------------------------------------------------
# Fallback: batch OpenAI Whisper engine
# ---------------------------------------------------------------------------

class _WhisperEngine:
    def __init__(self, on_partial, on_final, on_status):
        self._on_partial = on_partial
        self._on_final   = on_final
        self._on_status  = on_status
        self._active  = False
        self._running = False
        self._thread  = None
        self._audio   = None
        self._stream  = None
        self._client  = None

    @property
    def active(self):
        return self._active

    def start(self):
        api_key = os.environ.get("OPENAI_API_KEY", "")
        self._client = OpenAI(api_key=api_key)
        self._audio  = pyaudio.PyAudio()
        try:
            self._stream = self._audio.open(
                format=_FORMAT, channels=_CHANNELS, rate=_RATE,
                input=True, frames_per_buffer=_CHUNK,
            )
        except Exception as e:
            print(f"[whisper] Mic error: {e}")
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def begin(self):
        self._active = True

    def end(self):
        self._active = False

    def stop(self):
        self._running = False
        self._active  = False
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
        if self._audio:
            self._audio.terminate()

    def _loop(self):
        buf, silence, in_speech = [], 0, False
        while self._running:
            try:
                chunk = self._stream.read(_CHUNK, exception_on_overflow=False)
            except Exception:
                time.sleep(0.05)
                continue
            if not self._active:
                buf, silence, in_speech = [], 0, False
                time.sleep(0.01)
                continue
            rms = _rms(chunk)
            if rms > config.DICTATION_VAD_ENERGY_THRESH:
                buf.append(chunk)
                in_speech = True
                silence   = 0
            elif in_speech:
                buf.append(chunk)
                silence += 1
                if silence >= _SILENCE_CHUNKS:
                    if len(buf) >= _MIN_SPEECH_CHUNKS:
                        self._transcribe(buf)
                    buf, silence, in_speech = [], 0, False
            else:
                silence = 0

    def _transcribe(self, frames):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(_CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(_RATE)
            wf.writeframes(b"".join(frames))
        try:
            resp = self._client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.wav", buf.getvalue(), "audio/wav"),
                language="en",
            )
            text = resp.text.strip()
            if text:
                self._on_final(text)
        except Exception as e:
            print(f"[whisper] Error: {e}")


# --- Helpers ---

def _rms(data: bytes) -> float:
    count = len(data) // 2
    if count == 0:
        return 0.0
    shorts = struct.unpack(f"{count}h", data)
    return (sum(s * s for s in shorts) / count) ** 0.5


def _type_text(text: str):
    try:
        from pynput import keyboard as _kb
        _kb.Controller().type(text)
    except Exception as e:
        print(f"[dictation] type error: {e}")


def _press_enter():
    try:
        from pynput import keyboard as _kb
        from pynput.keyboard import Key
        ctrl = _kb.Controller()
        ctrl.press(Key.enter)
        ctrl.release(Key.enter)
    except Exception as e:
        print(f"[dictation] enter error: {e}")
