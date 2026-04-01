"""Whisper-based continuous dictation engine.

Lifecycle:
  engine.start()      — opens mic stream, starts capture thread (idle by default)
  engine.begin()      — enter dictation mode: accumulate + transcribe audio
  engine.end()        — exit dictation mode: flush remaining audio
  engine.stop()       — shut down completely

While active, uses a simple energy VAD:
  - Speech detected when RMS > VAD_ENERGY_THRESH
  - Sentence boundary when silence >= VAD_SILENCE_MS after speech
  - Sends WAV buffer to Whisper API, types result via pynput
"""

import io
import os
import struct
import threading
import time
import wave
import pyaudio
import config

try:
    from openai import OpenAI
    _openai_available = True
except ImportError:
    _openai_available = False

# --- VAD constants ---
_RATE      = 16000
_CHANNELS  = 1
_FORMAT    = pyaudio.paInt16
_CHUNK     = 1024           # ~64ms at 16kHz
_SILENCE_MS       = 700     # ms of silence before flushing segment
_SILENCE_CHUNKS   = int(_SILENCE_MS / (_CHUNK / _RATE * 1000))
_MIN_SPEECH_CHUNKS = 5      # ~320ms minimum to avoid transcribing noise


class DictationEngine:
    def __init__(self, on_status=None):
        """on_status(str) called with 'active'/'idle'/'error' status updates."""
        self._on_status = on_status or (lambda s: None)
        self._active    = False
        self._running   = False
        self._thread    = None
        self._audio     = None
        self._stream    = None
        self._client    = None
        self._lock      = threading.Lock()

    @property
    def active(self):
        return self._active

    def start(self):
        """Open mic and start background thread (idle mode)."""
        if not _openai_available:
            print("[dictation] openai package not installed.")
            return

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key or api_key.startswith("sk-your"):
            print("[dictation] OPENAI_API_KEY not set — dictation disabled.")
            return

        self._client = OpenAI(api_key=api_key)
        self._audio = pyaudio.PyAudio()
        try:
            self._stream = self._audio.open(
                format=_FORMAT,
                channels=_CHANNELS,
                rate=_RATE,
                input=True,
                frames_per_buffer=_CHUNK,
            )
        except Exception as e:
            print(f"[dictation] Could not open mic: {e}")
            self._audio.terminate()
            return

        self._running = True
        self._thread  = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print("[dictation] Ready. Say 'dictate' to start, 'stop dictating' to end.")

    def begin(self):
        """Enter dictation mode."""
        with self._lock:
            if not self._running:
                print("[dictation] Engine not started.")
                return
            self._active = True
        self._on_status("active")
        print("[dictation] Dictation ON — speak freely.")

    def end(self):
        """Exit dictation mode."""
        with self._lock:
            self._active = False
        self._on_status("idle")
        print("[dictation] Dictation OFF.")

    def stop(self):
        """Shut down completely."""
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

    # --- Internal ---

    def _capture_loop(self):
        speech_buf    = []
        silence_count = 0
        in_speech     = False

        while self._running:
            try:
                chunk = self._stream.read(_CHUNK, exception_on_overflow=False)
            except Exception:
                time.sleep(0.05)
                continue

            with self._lock:
                active = self._active

            if not active:
                # Drain without accumulating
                speech_buf    = []
                silence_count = 0
                in_speech     = False
                time.sleep(0.01)
                continue

            rms = _rms(chunk)

            if rms > config.DICTATION_VAD_ENERGY_THRESH:
                speech_buf.append(chunk)
                in_speech     = True
                silence_count = 0
            elif in_speech:
                speech_buf.append(chunk)  # keep a bit of trailing silence
                silence_count += 1
                if silence_count >= _SILENCE_CHUNKS:
                    # Segment complete — transcribe
                    if len(speech_buf) >= _MIN_SPEECH_CHUNKS:
                        self._transcribe(speech_buf)
                    speech_buf    = []
                    silence_count = 0
                    in_speech     = False
            else:
                silence_count = 0

    def _transcribe(self, frames):
        """Send frames (list of bytes) to Whisper, type result."""
        wav_bytes = _frames_to_wav(frames)
        try:
            response = self._client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.wav", wav_bytes, "audio/wav"),
                language="en",
            )
            text = response.text.strip()
            if text:
                print(f"[dictation] → '{text}'")
                _type_text(text + " ")
        except Exception as e:
            print(f"[dictation] Whisper error: {e}")


# --- Helpers ---

def _rms(data: bytes) -> float:
    """Root-mean-square energy of a raw PCM int16 chunk."""
    count  = len(data) // 2
    shorts = struct.unpack(f"{count}h", data)
    if count == 0:
        return 0.0
    return (sum(s * s for s in shorts) / count) ** 0.5


def _frames_to_wav(frames) -> bytes:
    """Pack raw PCM frames into an in-memory WAV file, return bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(2)          # 16-bit = 2 bytes
        wf.setframerate(_RATE)
        wf.writeframes(b"".join(frames))
    return buf.getvalue()


def _type_text(text: str):
    """Type text at current cursor position via pynput."""
    try:
        from pynput import keyboard as _kb
        ctrl = _kb.Controller()
        ctrl.type(text)
    except Exception as e:
        print(f"[dictation] type error: {e}")
