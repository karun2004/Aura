"""
Dialogue manager — conversation context, turn memory, and session state.
"""

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DialogueManager:
    """Manages conversational context across turns and sessions."""

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self._turns: list[dict] = []
        self._session: dict = {
            "active_window": None,
            "active_tab": None,
            "last_search_results": [],
            "last_referenced_file": None,
            "last_referenced_element": None,
            "navigation_history": [],
        }

    def add_turn(self, role: str, content: str, intent: Optional[dict] = None):
        """Record a conversational turn."""
        self._turns.append({
            "role": role,      # "user" or "assistant"
            "content": content,
            "intent": intent,
            "timestamp": time.time(),
        })
        # Trim old turns
        if len(self._turns) > self.max_turns:
            self._turns = self._turns[-self.max_turns:]

    def resolve_reference(self, text: str) -> str:
        """
        Resolve pronouns and references using recent context.
        E.g. "open it" -> resolves "it" to last referenced file/item.
        """
        lower = text.lower().strip()

        # "it" / "that" / "that file" / "this" -> last referenced file or search result
        if lower in ("open it", "delete it", "open that", "delete that"):
            ref = self._session.get("last_referenced_file")
            if ref:
                action = lower.split()[0]
                return f"{action} {ref}"

        # "go back" -> pop from navigation history
        if lower == "go back":
            history = self._session.get("navigation_history", [])
            if len(history) >= 2:
                return f"navigate to {history[-2]}"

        return text

    def get_session(self, key: str, default: Any = None) -> Any:
        return self._session.get(key, default)

    def update_session(self, key: str, value: Any):
        self._session[key] = value

        # Track navigation history
        if key == "active_tab" and value:
            history = self._session.setdefault("navigation_history", [])
            history.append(value)
            if len(history) > 50:
                self._session["navigation_history"] = history[-50:]

    def get_recent_context(self, n_turns: int = 5) -> str:
        """Get recent conversation as a string for LLM context."""
        recent = self._turns[-n_turns:]
        lines = []
        for turn in recent:
            prefix = "User" if turn["role"] == "user" else "AURA"
            lines.append(f"{prefix}: {turn['content']}")
        return "\n".join(lines)

    def clear(self):
        """Clear all turn context (session state persists)."""
        self._turns.clear()
