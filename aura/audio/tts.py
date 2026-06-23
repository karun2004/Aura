"""
Text-to-speech — speaks AURA's responses using Piper TTS.
Supports barge-in (interruption), adjustable speech rate, and warm personality.
"""

import io
import logging
import threading
import wave
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class SpeechSynthesizer:
    """Local, offline TTS with Piper and barge-in support."""

    def __init__(self, voice: str = "en_US-lessac-medium", speech_rate: float = 1.0):
        self.voice = voice
        self.speech_rate = speech_rate
        self._speaking = False
        self._interrupt_flag = threading.Event()
        self._play_thread: Optional[threading.Thread] = None
        self._piper = None

    def _ensure_piper(self):
        """Lazy-load Piper TTS on first use."""
        if self._piper is None:
            try:
                from piper import PiperVoice

                # Piper auto-downloads voice models on first use
                self._piper = PiperVoice.load(self.voice)
                logger.info(f"Piper TTS loaded: {self.voice}")
            except Exception:
                # Fallback: use piper-tts CLI wrapper via subprocess
                logger.warning("PiperVoice direct load failed, will use CLI fallback")
                self._piper = "cli_fallback"

    def speak(self, text: str, blocking: bool = False, priority: str = "normal"):
        """
        Synthesize and speak text.

        Args:
            text: Text to speak.
            blocking: If True, wait until speech finishes.
            priority: 'normal' or 'safety' (for confirmation prompts).
        """
        if not text.strip():
            return

        self._interrupt_flag.clear()
        self._speaking = True

        if blocking:
            self._speak_internal(text)
        else:
            self._play_thread = threading.Thread(
                target=self._speak_internal, args=(text,), daemon=True
            )
            self._play_thread.start()

    def _speak_internal(self, text: str):
        """Internal method that does the actual synthesis + playback."""
        try:
            audio_data = self._synthesize(text)
            if audio_data is not None:
                self._play_audio(audio_data)
        except Exception as e:
            logger.error(f"TTS error: {e}")
        finally:
            self._speaking = False

    def _synthesize(self, text: str) -> Optional[bytes]:
        """Synthesize text to raw audio bytes."""
        self._ensure_piper()

        try:
            if self._piper == "cli_fallback":
                return self._synthesize_cli(text)

            # Direct PiperVoice synthesis
            audio_buffer = io.BytesIO()
            with wave.open(audio_buffer, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(22050)
                self._piper.synthesize(text, wav, length_scale=1.0 / self.speech_rate)
            return audio_buffer.getvalue()
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            return self._synthesize_cli(text)

    def _synthesize_cli(self, text: str) -> Optional[bytes]:
        """Fallback: synthesize using piper CLI via subprocess."""
        import subprocess

        try:
            result = subprocess.run(
                ["piper", "--model", self.voice, "--output-raw"],
                input=text.encode(),
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except FileNotFoundError:
            logger.error("piper CLI not found — install with: pip install piper-tts")
        except Exception as e:
            logger.error(f"CLI synthesis error: {e}")
        return None

    def _play_audio(self, audio_data: bytes):
        """Play audio bytes with barge-in support (check interrupt flag periodically)."""
        try:
            import sounddevice as sd

            # Parse WAV or raw audio
            try:
                with io.BytesIO(audio_data) as f:
                    with wave.open(f, "rb") as wf:
                        sr = wf.getframerate()
                        frames = wf.readframes(wf.getnframes())
                        audio_np = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            except wave.Error:
                # Raw 16-bit audio at 22050 Hz
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                sr = 22050

            # Play in small chunks so we can check the interrupt flag
            chunk_size = sr // 4  # 250ms chunks
            for i in range(0, len(audio_np), chunk_size):
                if self._interrupt_flag.is_set():
                    logger.info("Speech interrupted (barge-in)")
                    return
                chunk = audio_np[i : i + chunk_size]
                sd.play(chunk, samplerate=sr)
                sd.wait()

        except ImportError:
            logger.warning("sounddevice not available, trying simpleaudio")
            self._play_audio_simpleaudio(audio_data)

    def _play_audio_simpleaudio(self, audio_data: bytes):
        """Fallback player using simpleaudio."""
        try:
            import simpleaudio as sa

            with io.BytesIO(audio_data) as f:
                with wave.open(f, "rb") as wf:
                    play_obj = sa.play_buffer(
                        wf.readframes(wf.getnframes()),
                        num_channels=wf.getnchannels(),
                        bytes_per_sample=wf.getsampwidth(),
                        sample_rate=wf.getframerate(),
                    )
                    while play_obj.is_playing():
                        if self._interrupt_flag.is_set():
                            play_obj.stop()
                            return
        except Exception as e:
            logger.error(f"simpleaudio playback error: {e}")

    def interrupt(self):
        """Immediately stop any ongoing speech (barge-in)."""
        self._interrupt_flag.set()
        self._speaking = False

    def is_speaking(self) -> bool:
        return self._speaking

    def wait(self):
        """Block until current speech finishes."""
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join()
