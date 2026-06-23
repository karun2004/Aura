"""
Speech-to-text — converts spoken commands to text using faster-whisper.
GPU-accelerated by default, CPU fallback if no GPU available.
"""

import logging
import time
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000


class SpeechRecognizer:
    """Local, offline speech-to-text using faster-whisper."""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "auto",
        language: str = "en",
        vocabulary_bias: Optional[list] = None,
    ):
        self.model_size = model_size
        self.device = device
        self.language = language
        self.vocabulary_bias = vocabulary_bias or []
        self._model = None

    def load_model(self):
        """Load the Whisper model with GPU acceleration if available."""
        from faster_whisper import WhisperModel
        import torch

        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        compute_type = "float16" if self.device == "cuda" else "int8"
        logger.info(f"Loading Whisper '{self.model_size}' on {self.device} ({compute_type})")

        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=compute_type,
        )
        logger.info("ASR model loaded")

    def transcribe(self, audio_data: np.ndarray) -> str:
        """
        Transcribe audio to text.

        Args:
            audio_data: numpy array of audio samples (16kHz, float32 or int16).

        Returns:
            Transcribed text string.
        """
        if self._model is None:
            self.load_model()

        # Convert int16 to float32 if needed
        if audio_data.dtype == np.int16:
            audio_data = audio_data.astype(np.float32) / 32768.0

        start = time.time()
        segments, info = self._model.transcribe(
            audio_data,
            language=self.language,
            beam_size=5,
            vad_filter=True,  # skip silence segments for speed
        )

        text = " ".join(seg.text.strip() for seg in segments).strip()
        elapsed = time.time() - start
        logger.info(f"Transcribed in {elapsed:.2f}s: '{text}'")
        return text


def record_until_silence(
    timeout: float = 8.0,
    silence_duration: float = 1.5,
    silence_threshold: int = 500,
) -> np.ndarray:
    """
    Record audio from microphone until silence is detected or timeout.

    Args:
        timeout: Maximum recording time in seconds.
        silence_duration: How long silence must persist to stop (seconds).
        silence_threshold: RMS amplitude below which audio counts as silence.

    Returns:
        numpy array of recorded audio (16kHz, int16).
    """
    import pyaudio

    CHUNK = 1024
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    frames = []
    silent_chunks = 0
    silent_chunks_needed = int(silence_duration * SAMPLE_RATE / CHUNK)
    max_chunks = int(timeout * SAMPLE_RATE / CHUNK)

    logger.debug(f"Recording (timeout={timeout}s, silence={silence_duration}s)...")

    try:
        for i in range(max_chunks):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)

            audio_chunk = np.frombuffer(data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))

            if rms < silence_threshold:
                silent_chunks += 1
            else:
                silent_chunks = 0

            # Only stop on silence if we have at least some audio
            if silent_chunks >= silent_chunks_needed and len(frames) > silent_chunks_needed + 5:
                logger.debug("Silence detected, stopping recording")
                break
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()

    audio = np.frombuffer(b"".join(frames), dtype=np.int16)
    logger.debug(f"Recorded {len(audio)/SAMPLE_RATE:.1f}s of audio")
    return audio
