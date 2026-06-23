#!/usr/bin/env python3
"""
AURA — main entry point.
Starts the voice interaction loop: Wake Word → ASR → Intent → Action → TTS
"""

import argparse
import logging
import sys

from aura.audio.wake_word import WakeWordDetector
from aura.audio.asr import SpeechRecognizer, record_until_silence
from aura.audio.tts import SpeechSynthesizer
from aura.audio.cues import AudioCues, AuraState
from aura.dialogue.intent import IntentClassifier
from aura.dialogue.manager import DialogueManager
from aura.actions.executor import ActionExecutor
from aura.accessibility.bridge import AccessibilityBridge
from aura.safety.classifier import SafetyClassifier, RiskLevel
from aura.config.profile import UserProfile
from aura.llm.engine import LocalLLM

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("aura")


class Aura:
    """Main AURA application — orchestrates all subsystems."""

    def __init__(self, model_path=None, verbose=False):
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        logger.info("Initializing AURA...")

        # Load subsystems
        self.profile = UserProfile()
        self.cues = AudioCues()
        self.tts = SpeechSynthesizer(
            speech_rate=self.profile.get("speech_rate", 1.0)
        )
        self.asr = SpeechRecognizer(device="auto")
        self.accessibility = AccessibilityBridge()
        self.executor = ActionExecutor()
        self.dialogue = DialogueManager()
        self.safety = SafetyClassifier()

        # LLM (optional — works without it, just less flexible)
        self.llm = LocalLLM()
        llm_for_intent = self.llm if self.llm.is_available() else None
        self.intent_classifier = IntentClassifier(llm_engine=llm_for_intent)

        # Wake word detector
        self.wake_detector = WakeWordDetector(
            model_path=model_path,
            on_detected=self._on_wake_word,
        )

        logger.info("AURA initialized")

    def start(self):
        """Start the main voice interaction loop."""
        self.tts.speak("AURA is ready.", blocking=True)
        logger.info("Starting wake word detection...")

        try:
            self.wake_detector.start(blocking=True)
        except FileNotFoundError as e:
            logger.error(str(e))
            self.tts.speak(
                "I couldn't find my wake word model. "
                "Please check the models folder or train a new model.",
                blocking=True,
            )
            sys.exit(1)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        """Clean shutdown."""
        logger.info("Shutting down AURA...")
        self.wake_detector.stop()
        self.tts.speak("Goodbye.", blocking=True)

    def _on_wake_word(self):
        """Called when 'Hey AURA' is detected — runs the full interaction cycle."""
        self.cues.play(AuraState.WAKE_DETECTED, blocking=True)

        # 1. Record user's command
        self.cues.play(AuraState.LISTENING)
        audio = record_until_silence(timeout=8.0, silence_duration=1.5)

        # 2. Transcribe
        self.cues.play(AuraState.THINKING)
        text = self.asr.transcribe(audio)

        if not text.strip():
            self.tts.speak("I didn't catch that. Try again?")
            return

        logger.info(f"User said: '{text}'")
        self.dialogue.add_turn("user", text)

        # 3. Resolve references ("it", "that file", etc.)
        resolved_text = self.dialogue.resolve_reference(text)

        # 4. Classify intent
        intent = self.intent_classifier.classify(resolved_text)
        logger.info(f"Intent: {intent.action} (tier={intent.tier.name}, conf={intent.confidence})")

        # 5. Handle the intent
        response = self._handle_intent(intent)

        # 6. Speak response
        if response:
            self.dialogue.add_turn("assistant", response, intent={"action": intent.action})
            self.tts.speak(response)
            self.cues.play(AuraState.DONE)

    def _handle_intent(self, intent) -> str:
        """Route an intent to the appropriate handler and return a spoken response."""
        action = intent.action
        params = intent.parameters

        # ---- Stop / Cancel ----
        if action == "stop":
            self.tts.interrupt()
            return ""

        # ---- Window / Tab Queries ----
        if action == "get_active_window":
            info = self.accessibility.get_active_window()
            return f"You're in {info['app']}, window title: {info['title']}."

        if action == "get_current_tab":
            info = self.accessibility.get_active_window()
            return f"The current window is: {info['title']}."

        if action == "list_tabs":
            return "Tab listing requires the browser extension. It's not connected yet."

        # ---- Open Application ----
        if action == "open_app":
            success, msg = self.executor.open_application(params.get("app_name", ""))
            return msg

        # ---- Read Content ----
        if action == "read_content":
            mode = params.get("mode", "literal")
            content = self.accessibility.get_window_text()
            if not content.strip():
                return "I couldn't find any readable content in this window."

            if mode == "summary" and self.llm.is_available():
                self.cues.play(AuraState.THINKING)
                summary = self.llm.summarize(content)
                return summary
            else:
                # Literal mode: read first ~500 chars, offer to continue
                preview = content[:500].strip()
                if len(content) > 500:
                    return f"{preview}... That's the beginning. Say 'continue' to hear more."
                return preview

        # ---- Navigation ----
        if action == "navigate":
            target = params.get("target", "")
            # Check aliases first
            alias = self.profile.resolve_alias(target)
            if alias:
                target = alias.get("target", target)
            return f"Navigation to '{target}' requires the browser extension or accessibility bridge. This is being implemented."

        if action == "go_back":
            return "Go back is not yet fully implemented."

        if action == "click":
            target = params.get("target", "")
            elem = self.accessibility.find_element(name=target)
            if elem:
                return f"Found element: {elem['name']} ({elem['role']}). Click action coming in a future update."
            return f"I couldn't find '{target}' on this page."

        # ---- File Operations ----
        if action == "file_search":
            query = params.get("query", "")
            results = self.executor.file_search(query)
            if not results:
                return f"I couldn't find any files matching '{query}'."

            self.dialogue.update_session("last_search_results", results)
            self.dialogue.update_session("last_referenced_file", results[0]["path"])

            if len(results) == 1:
                r = results[0]
                return f"Found {r['name']} at {r['path']}. Say 'open it' to open."
            else:
                names = ", ".join(r["name"] for r in results[:5])
                return f"Found {len(results)} files: {names}. Say 'open it' to open the first one."

        if action == "open_last_result":
            path = self.dialogue.get_session("last_referenced_file")
            if path:
                success, msg = self.executor.file_open(path)
                return msg
            return "I don't have a file to open. Try searching for one first."

        if action == "file_save":
            return "File saving requires the active application's save dialog. This is being implemented."

        if action == "create_folder":
            name = params.get("name", "")
            # Safety check
            risk = self.safety.classify("create_folder")
            success, msg = self.executor.create_folder(name)
            return msg

        if action in ("delete", "delete_current"):
            target = params.get("target", "")
            if action == "delete_current":
                target = self.dialogue.get_session("last_referenced_file", "")

            if not target:
                return "What would you like me to delete?"

            # Safety: always confirm
            risk = self.safety.classify("delete")
            if self.safety.requires_confirmation(risk):
                return f"Are you sure you want to delete '{Path(target).name}'? Say 'yes' to confirm or 'cancel' to stop."
            # Note: actual deletion after confirmation is handled in a follow-up turn
            # Full confirmation flow is Goal 32

        # ---- Verbosity ----
        if action == "set_verbosity":
            level = params.get("level", "normal")
            self.profile.set("verbosity", level)
            return f"Verbosity set to {level}."

        # ---- Help ----
        if action == "help":
            return (
                "I can help you with: opening applications, reading what's on screen, "
                "finding and managing files, navigating websites, and answering questions "
                "about what you see. Just say Hey AURA followed by what you need."
            )

        # ---- Unknown ----
        if action == "unknown":
            if self.llm.is_available():
                # Try to handle as a general question via LLM
                self.cues.play(AuraState.THINKING)
                response = self.llm.generate(
                    f"The user said: '{intent.raw_text}'. Give a brief, helpful spoken response.",
                    system="You are AURA, a helpful voice assistant. Keep responses brief and spoken-friendly."
                )
                return response
            return "I'm not sure what you mean. Could you rephrase that?"

        return f"The '{action}' feature is still being built."


from pathlib import Path  # noqa: E402 (imported here to avoid circular at top)


def main():
    parser = argparse.ArgumentParser(description="AURA Voice Assistant")
    parser.add_argument("--model", type=str, default=None,
                        help="Path to wake word .onnx model")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--no-wake-word", action="store_true",
                        help="Skip wake word detection — start listening immediately (for testing)")
    args = parser.parse_args()

    aura = Aura(model_path=args.model, verbose=args.verbose)

    if args.no_wake_word:
        # Test mode: skip wake word, just run one interaction cycle
        logger.info("Test mode — skipping wake word, recording immediately...")
        aura.tts.speak("Test mode. Listening for your command.", blocking=True)
        aura._on_wake_word()
    else:
        aura.start()


if __name__ == "__main__":
    main()
