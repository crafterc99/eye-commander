"""Wispr Flow WebSocket streaming transcription engine.

Streams 16kHz mono PCM audio in real-time, receives partial + final
transcriptions. Falls back gracefully if WISPR_API_KEY not set.

Usage:
  engine = WisprDictationEngine(on_partial=..., on_final=..., on_status=...)
  engine.start()   # open mic + connect WebSocket
  engine.begin()   # start streaming audio
  engine.end()     # commit session, stop streaming
  engine.stop()    # full shutdown
"""

import asyncio
import base64
import io
import json
import os
import struct
import threading
import time
import wave
import pyaudio

_RATE             = 16000
_CHANNELS         = 1
_FORMAT           = pyaudio.paInt16
_CHUNK            = 1024                      # 64ms per packet
_PACKET_DURATION  = _CHUNK / _RATE            # 0.064 s
_WS_URL           = "wss://platform-api.wisprflow.ai/api/v1/dash/ws?api_key=Bearer%20{key}"


class WisprDictationEngine:
    def __init__(self, on_partial=None, on_final=None, on_status=None):
        self._on_partial = on_partial or (lambda t: None)
        self._on_final   = on_final   or (lambda t: None)
        self._on_status  = on_status  or (lambda s: None)

        self._active   = False
        self._running  = False
        self._ws       = None
        self._loop     = None
        self._thread   = None
        self._audio    = None
        self._stream   = None
        self._position = 0
        self._lock     = threading.Lock()
        self._ready    = threading.Event()   # set when WS auth succeeds

    @property
    def active(self):
        return self._active

    def start(self) -> bool:
        """Open mic, connect WebSocket. Returns True if successful."""
        api_key = os.environ.get("WISPR_API_KEY", "")
        if not api_key or api_key.startswith("your"):
            print("[wispr] WISPR_API_KEY not set — Wispr Flow disabled.")
            return False

        self._api_key = api_key
        self._audio = pyaudio.PyAudio()
        try:
            self._stream = self._audio.open(
                format=_FORMAT, channels=_CHANNELS, rate=_RATE,
                input=True, frames_per_buffer=_CHUNK,
            )
        except Exception as e:
            print(f"[wispr] Mic error: {e}")
            self._audio.terminate()
            return False

        self._loop   = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=8)          # wait up to 8s for auth
        if self._ready.is_set():
            print("[wispr] Wispr Flow streaming ready.")
            return True
        else:
            print("[wispr] Wispr Flow connection timed out.")
            return False

    def begin(self):
        """Start streaming audio to Wispr."""
        with self._lock:
            self._active   = True
            self._position = 0
        self._on_status("active")
        print("[wispr] Streaming started.")

    def end(self):
        """Commit session and stop streaming."""
        with self._lock:
            self._active = False
            pos = self._position
        if self._loop and self._ws:
            asyncio.run_coroutine_threadsafe(
                self._send_commit(pos), self._loop
            )
        self._on_status("idle")
        print("[wispr] Session committed.")

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
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    # --- asyncio internals ---

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._running = True
        self._loop.run_until_complete(self._ws_main())

    async def _ws_main(self):
        import websockets
        url = _WS_URL.format(key=self._api_key)
        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    self._ws = ws
                    # Authenticate
                    await ws.send(json.dumps({
                        "type": "auth",
                        "access_token": self._api_key,
                        "language": ["en"],
                        "context": {"app": "eye-commander"},
                    }))
                    await asyncio.gather(
                        self._capture_loop(ws),
                        self._receive_loop(ws),
                    )
            except Exception as e:
                print(f"[wispr] WS error: {e}")
                self._ws = None
                self._ready.clear()
                await asyncio.sleep(3)

    async def _capture_loop(self, ws):
        """Read mic and stream audio packets when active."""
        loop = asyncio.get_event_loop()
        while self._running:
            chunk = await loop.run_in_executor(
                None, lambda: self._stream.read(_CHUNK, exception_on_overflow=False)
            )
            with self._lock:
                active = self._active
                pos    = self._position
                if active:
                    self._position += 1

            if active:
                wav_b64 = _chunk_to_b64_wav(chunk)
                rms     = _rms_norm(chunk)
                try:
                    await ws.send(json.dumps({
                        "type": "append",
                        "position": pos,
                        "audio_packets": {
                            "packets": [wav_b64],
                            "volumes": [rms],
                            "packet_duration": _PACKET_DURATION,
                            "audio_encoding": "wav",
                            "byte_encoding": "base64",
                        },
                    }))
                except Exception:
                    return  # will reconnect

    async def _receive_loop(self, ws):
        """Receive transcription responses."""
        async for raw in ws:
            try:
                data   = json.loads(raw)
                status = data.get("status")
                if status == "auth":
                    self._ready.set()
                elif status == "text":
                    text  = data.get("body", {}).get("text", "").strip()
                    final = data.get("final", False)
                    if text:
                        if final:
                            self._on_final(text)
                        else:
                            self._on_partial(text)
            except Exception:
                pass

    async def _send_commit(self, total_packets):
        if self._ws:
            try:
                await self._ws.send(json.dumps({
                    "type": "commit",
                    "total_packets": total_packets,
                }))
            except Exception:
                pass


# --- Helpers ---

def _chunk_to_b64_wav(chunk: bytes) -> str:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(_RATE)
        wf.writeframes(chunk)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _rms_norm(data: bytes) -> float:
    count = len(data) // 2
    if count == 0:
        return 0.0
    shorts = struct.unpack(f"{count}h", data)
    rms = (sum(s * s for s in shorts) / count) ** 0.5
    return min(1.0, rms / 32768.0)
