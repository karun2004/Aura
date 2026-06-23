"""
User Profile & Settings — persistent local storage for preferences.

Stores: verbosity level, speech rate, learned aliases (e.g. "IEP" -> dashboard URL),
frequently used apps, and confirmed dangerous-action patterns.

Stored locally on the device by default. Never required to leave the device.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_PATH = Path.home() / ".config" / "aura" / "profile.json"


class UserProfile:
    """Persistent user preferences and learned data."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or DEFAULT_PROFILE_PATH
        self._data: dict = {
            "verbosity": "normal",  # "brief", "normal", "detailed"
            "speech_rate": 1.0,
            "aliases": {},          # e.g. {"IEP": {"type": "url", "target": "..."}}
            "frequent_apps": [],
        }
        self._load()

    def _load(self):
        """Load profile from disk if it exists."""
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
                logger.info(f"User profile loaded from {self.path}")
            except Exception as e:
                logger.warning(f"Could not load profile: {e}")

    def save(self):
        """Persist profile to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value
        self.save()

    def add_alias(self, phrase: str, target: dict):
        """Teach AURA a new alias (e.g. 'IEP' -> specific page)."""
        self._data["aliases"][phrase.lower()] = target
        self.save()

    def resolve_alias(self, phrase: str) -> Optional[dict]:
        """Look up a taught alias."""
        return self._data["aliases"].get(phrase.lower())
