"""
Intent classifier — Tier 1 grammar + Tier 2 LLM fallback.
Tier 1 handles common structural commands instantly via pattern matching.
Tier 2 routes to the local LLM for flexible/ambiguous phrasing.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class IntentTier(Enum):
    GRAMMAR = 1
    LOCAL_LLM = 2
    CLOUD_LLM = 3


@dataclass
class Intent:
    action: str
    parameters: dict = field(default_factory=dict)
    confidence: float = 1.0
    tier: IntentTier = IntentTier.GRAMMAR
    raw_text: str = ""


# Tier 1: Pattern-based grammar rules
# Each rule: (compiled regex, action_name, parameter_extractor_function)
GRAMMAR_RULES = [
    # Stop / Cancel (highest priority)
    (re.compile(r"^(stop|cancel|quit|never\s*mind|shut\s*up)$", re.I),
     "stop", lambda m: {}),

    # Open application
    (re.compile(r"^open\s+(?:the\s+)?(.+)$", re.I),
     "open_app", lambda m: {"app_name": m.group(1).strip()}),

    # Tab queries
    (re.compile(r"^what\s+tab\s+(?:am\s+i\s+on|is\s+(?:this|active|focused))[\?]?$", re.I),
     "get_current_tab", lambda m: {}),
    (re.compile(r"^(?:what|which|list|show)\s+tabs?\s+(?:do\s+i\s+have|are)\s+open[\?]?$", re.I),
     "list_tabs", lambda m: {}),
    (re.compile(r"^(?:list|show)\s+(?:my\s+)?(?:open\s+)?tabs?$", re.I),
     "list_tabs", lambda m: {}),

    # Read content
    (re.compile(r"^read\s+(?:this|the)?\s*(?:page|content|screen)?\s*(?:to\s+me)?$", re.I),
     "read_content", lambda m: {"mode": "literal"}),
    (re.compile(r"^(?:give\s+me\s+(?:a|the)\s+)?summar(?:y|ize)\s*(?:this)?(?:\s+page)?$", re.I),
     "read_content", lambda m: {"mode": "summary"}),
    (re.compile(r"^just\s+(?:give\s+me\s+)?(?:the\s+)?summary$", re.I),
     "read_content", lambda m: {"mode": "summary"}),
    (re.compile(r"^what(?:'s|\s+is)\s+on\s+(?:this|the)\s+(?:page|screen)[\?]?$", re.I),
     "read_content", lambda m: {"mode": "summary"}),

    # Navigation
    (re.compile(r"^(?:go\s+to|navigate\s+to|open)\s+(.+)$", re.I),
     "navigate", lambda m: {"target": m.group(1).strip()}),
    (re.compile(r"^(?:next|go\s+to\s+(?:the\s+)?next)\s+(heading|link|button|field|table)$", re.I),
     "navigate_next", lambda m: {"element_type": m.group(1).lower()}),
    (re.compile(r"^(?:previous|go\s+to\s+(?:the\s+)?previous)\s+(heading|link|button|field|table)$", re.I),
     "navigate_prev", lambda m: {"element_type": m.group(1).lower()}),
    (re.compile(r"^go\s*back$", re.I),
     "go_back", lambda m: {}),
    (re.compile(r"^click\s+(?:the\s+)?(?:on\s+)?(.+)$", re.I),
     "click", lambda m: {"target": m.group(1).strip()}),

    # File operations
    (re.compile(r"^find\s+(?:the\s+)?(?:file\s+)?(?:called\s+|named\s+)?(.+)$", re.I),
     "file_search", lambda m: {"query": m.group(1).strip()}),
    (re.compile(r"^open\s+it$", re.I),
     "open_last_result", lambda m: {}),
    (re.compile(r"^save\s+(?:this\s+)?(?:as\s+)?(.+?)(?:\s+in\s+(.+))?$", re.I),
     "file_save", lambda m: {"name": m.group(1).strip(), "folder": (m.group(2) or "").strip()}),
    (re.compile(r"^create\s+(?:a\s+)?(?:new\s+)?folder\s+(?:called\s+|named\s+)?(.+)$", re.I),
     "create_folder", lambda m: {"name": m.group(1).strip()}),
    (re.compile(r"^delete\s+(?:this\s+)?(?:file\s+)?(?:called\s+|named\s+)?(.+)$", re.I),
     "delete", lambda m: {"target": m.group(1).strip()}),
    (re.compile(r"^delete\s+(?:this|it)$", re.I),
     "delete_current", lambda m: {}),

    # Window queries
    (re.compile(r"^what\s+(?:app|application|window|program)\s+(?:am\s+i\s+(?:in|on|using)|is\s+(?:this|open|active))[\?]?$", re.I),
     "get_active_window", lambda m: {}),

    # Verbosity control
    (re.compile(r"^(?:be\s+)?more\s+(?:brief|concise|short)$", re.I),
     "set_verbosity", lambda m: {"level": "brief"}),
    (re.compile(r"^(?:give\s+me\s+)?more\s+detail$", re.I),
     "set_verbosity", lambda m: {"level": "detailed"}),

    # Help
    (re.compile(r"^(?:help|what\s+can\s+you\s+do)[\?]?$", re.I),
     "help", lambda m: {}),
]


class IntentClassifier:
    """Tiered intent classification — fast grammar first, LLM fallback."""

    def __init__(self, llm_engine=None):
        self.llm = llm_engine

    def classify(self, text: str, context: Optional[dict] = None) -> Intent:
        """
        Classify user text into an actionable intent.
        Tries Tier 1 grammar first. Falls back to Tier 2 LLM if no match.
        """
        text = text.strip()
        if not text:
            return Intent(action="empty", raw_text=text, confidence=0.0)

        # Tier 1: Grammar matching
        for pattern, action, param_fn in GRAMMAR_RULES:
            match = pattern.match(text)
            if match:
                params = param_fn(match)
                logger.debug(f"Tier 1 match: '{text}' -> {action}({params})")
                return Intent(
                    action=action,
                    parameters=params,
                    confidence=1.0,
                    tier=IntentTier.GRAMMAR,
                    raw_text=text,
                )

        # Tier 2: Local LLM classification
        if self.llm:
            return self._classify_with_llm(text, context)

        # No match and no LLM available
        logger.warning(f"No intent match for: '{text}'")
        return Intent(
            action="unknown",
            parameters={"original_text": text},
            confidence=0.0,
            tier=IntentTier.GRAMMAR,
            raw_text=text,
        )

    def _classify_with_llm(self, text: str, context: Optional[dict] = None) -> Intent:
        """Use local LLM to classify ambiguous commands."""
        prompt = f"""You are a voice command classifier for a screen reader assistant.
Classify this command into one action. Reply with ONLY a JSON object.

Available actions: open_app, navigate, read_content, file_search, file_save,
create_folder, delete, get_current_tab, list_tabs, get_active_window, click,
go_back, help, unknown

Command: "{text}"

Reply format: {{"action": "...", "parameters": {{...}}}}"""

        try:
            response = self.llm.generate(prompt, max_tokens=100)
            import json
            # Try to parse JSON from response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1].strip()
                if response.startswith("json"):
                    response = response[4:].strip()
            data = json.loads(response)
            return Intent(
                action=data.get("action", "unknown"),
                parameters=data.get("parameters", {}),
                confidence=0.7,
                tier=IntentTier.LOCAL_LLM,
                raw_text=text,
            )
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
            return Intent(
                action="unknown",
                parameters={"original_text": text},
                confidence=0.0,
                tier=IntentTier.LOCAL_LLM,
                raw_text=text,
            )
