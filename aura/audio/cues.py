"""
Audio state cues — non-visual system state communication.
Generates simple sine-wave tones as cues (no external WAV files needed).
"""

import logging
import threading
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 22050


class AuraState(Enum):
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    DONE = "done"
    ERROR = "error"
    WAKE_DETECTED = "wake_detected"


# Each state maps to (frequency_hz, duration_seconds, pattern)
TONE_MAP = {
    AuraState.WAKE_DETECTED: [(880, 0.1), (1100, 0.1)],         # rising two-tone "ping"
    AuraState.LISTENING:     [(660, 0.15)],                       # single mid tone
    AuraState.THINKING:      [(440, 0.1), (440, 0.1)],           # double tap
    AuraState.DONE:          [(880, 0.08), (660, 0.08)],          # falling two-tone
    AuraState.ERROR:         [(330, 0.15), (220, 0.2)],           # low descending
    AuraState.SPEAKING:      [],                                   # no cue needed (speech itself is the feedback)
}


def _generate_tone(frequency: float, duration: float, volume: float = 0.3) -> np.ndarray:
    """Generate a sine wave tone as float32 numpy array."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    # Apply short fade in/out to avoid clicks
    tone = np.sin(2 * np.pi * frequency * t) * volume
    fade = min(int(SAMPLE_RATE * 0.01), len(tone) // 4)
    tone[:fade] *= np.linspace(0, 1, fade)
    tone[-fade:] *= np.linspace(1, 0, fade)
    return tone.astype(np.float32)


class AudioCues:
    """Plays short audio cues to communicate system state non-visually."""

    def __init__(self):
        self._player_available = True
        try:
            import sounddevice  # noqa: F401
        except ImportError:
            logger.warning("sounddevice not available — audio cues will be silent")
            self._player_available = False

    def play(self, state: AuraState, blocking: bool = False):
        """Play the audio cue for the given state."""
        tones = TONE_MAP.get(state, [])
        if not tones or not self._player_available:
            return

        if blocking:
            self._play_tones(tones)
        else:
            threading.Thread(target=self._play_tones, args=(tones,), daemon=True).start()

    def _play_tones(self, tones: list):
        """Play a sequence of tones."""
        try:
            import sounddevice as sd
            for freq, dur in tones:
                audio = _generate_tone(freq, dur)
                sd.play(audio, samplerate=SAMPLE_RATE)
                sd.wait()
        except Exception as e:
            logger.debug(f"Audio cue playback error: {e}")
