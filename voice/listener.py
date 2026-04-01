"""Vosk mic input in daemon thread — emits recognized command strings via callback."""

import json
import os
import queue
import threading
import pyaudio
import vosk
import config


class VoiceListener:
    def __init__(self, callback):
        """callback(phrase: str) called from daemon thread with lowercased phrase."""
        self._callback = callback
        self._q = queue.Queue()
        self._running = False
        self._thread = None

    def start(self):
        model_path = config.VOSK_MODEL_PATH
        if not os.path.exists(model_path):
            print(f"[voice] Vosk model not found at '{model_path}'. Voice commands disabled.")
            return
        model = vosk.Model(model_path)
        self._recognizer = vosk.KaldiRecognizer(model, config.VOSK_SAMPLE_RATE)
        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=config.VOSK_SAMPLE_RATE,
            input=True,
            frames_per_buffer=config.VOSK_CHUNK_SIZE,
        )
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print("[voice] Listening for commands.")

    def _listen_loop(self):
        while self._running:
            try:
                data = self._stream.read(config.VOSK_CHUNK_SIZE, exception_on_overflow=False)
                if self._recognizer.AcceptWaveform(data):
                    result = json.loads(self._recognizer.Result())
                    text = result.get("text", "").strip().lower()
                    if text:
                        self._callback(text)
            except Exception as e:
                print(f"[voice] Error: {e}")

    def stop(self):
        self._running = False
        if hasattr(self, "_stream"):
            self._stream.stop_stream()
            self._stream.close()
        if hasattr(self, "_audio"):
            self._audio.terminate()
