"""
Safety & Confirmation Layer — action risk classification and confirmation.

Every action is classified:
- Safe/Reversible: execute immediately, narrate result
- Moderate/Undoable: execute, clearly narrate what happened
- Destructive/Irreversible: ALWAYS double-confirm, no exceptions, no bypass

The global "stop/cancel" command pre-empts everything else at all times.
"""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    DESTRUCTIVE = "destructive"


class SafetyClassifier:
    """Classifies actions by risk level and enforces confirmation rules."""

    # Actions that always require double confirmation
    DESTRUCTIVE_ACTIONS = {
        "delete", "overwrite", "send_email", "send_message",
        "submit_form", "close_unsaved", "permanent_delete",
    }

    MODERATE_ACTIONS = {
        "create_folder", "type_text", "open_file",
    }

    def classify(self, action: str, parameters: dict = None) -> RiskLevel:
        """Classify an action's risk level."""
        if action in self.DESTRUCTIVE_ACTIONS:
            return RiskLevel.DESTRUCTIVE
        if action in self.MODERATE_ACTIONS:
            return RiskLevel.MODERATE
        return RiskLevel.SAFE

    def requires_confirmation(self, risk: RiskLevel) -> bool:
        """Whether this risk level requires explicit user confirmation."""
        return risk == RiskLevel.DESTRUCTIVE

    def requires_double_confirmation(self, action: str, parameters: dict = None) -> bool:
        """Whether this specific action requires a second confirmation."""
        # Multi-item deletes, permanent deletes, etc.
        if parameters and parameters.get("count", 1) > 1:
            return True
        if action == "permanent_delete":
            return True
        return False
