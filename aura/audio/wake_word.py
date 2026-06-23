"""
Wake word detection — always-on background listener for "Hey AURA".
Uses openWakeWord with a custom-trained ONNX model.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "hey_aura.onnx"
CHUNK_SIZE = 1280  # 80ms at 16kHz — openWakeWord's expected frame size
SAMPLE_RATE = 16000
SILENCE_TIMEOUT = 8.0  # seconds of silence before stopping listening after wake


class WakeWordDetector:
    """Continuously listens for the 'Hey AURA' wake word via microphone."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        threshold: float = 0.5,
        on_detected: Optional[Callable] = None,
    ):
        self.model_path = str(model_path or DEFAULT_MODEL_PATH)
        self.threshold = threshold
        self.on_detected = on_detected
        self._running = False
        self._model = None
        self._stream = None
        self._thread = None

    def load_model(self):
        """Load the openWakeWord model."""
        from openwakeword.model import Model

        if not Path(self.model_path).exists():
            raise FileNotFoundError(
                f"Wake word model not found at {self.model_path}. "
                "Train one using training/README.md or download from releases."
            )

        self._model = Model(
            wakeword_models=[self.model_path],
            inference_framework="onnx",
        )
        logger.info(f"Wake word model loaded: {self.model_path}")

    def start(self, blocking: bool = True):
        """Start continuous wake word detection."""
        if self._model is None:
            self.load_model()

        self._running = True
        if blocking:
            self._listen_loop()
        else:
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()

    def stop(self):
        """Stop listening."""
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("Wake word detection stopped")

    def _listen_loop(self):
        """Main listening loop — captures audio and checks for wake word."""
        import pyaudio

        pa = pyaudio.PyAudio()
        self._stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )

        logger.info("Listening for 'Hey AURA'...")

        try:
            while self._running:
                audio_bytes = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                audio_np = np.frombuffer(audio_bytes, dtype=np.int16)

                prediction = self._model.predict(audio_np)

                for model_name, score in prediction.items():
                    if score > self.threshold:
                        logger.info(f"Wake word detected! (score: {score:.3f})")
                        if self.on_detected:
                            self.on_detected()
                        # Reset predictions to avoid re-triggering
                        self._model.reset()
                        break
        except Exception as e:
            logger.error(f"Wake word listener error: {e}")
        finally:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
            pa.terminate()
