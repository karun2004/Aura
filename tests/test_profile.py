"""Tests for user profile storage."""

import tempfile
from pathlib import Path
from aura.config.profile import UserProfile


def test_alias_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "profile.json"
        profile = UserProfile(path=path)
        profile.add_alias("IEP", {"type": "url", "target": "https://example.com/iep"})
        result = profile.resolve_alias("iep")
        assert result is not None
        assert result["target"] == "https://example.com/iep"


def test_alias_case_insensitive():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "profile.json"
        profile = UserProfile(path=path)
        profile.add_alias("Hey Test", {"type": "nav", "target": "test_page"})
        assert profile.resolve_alias("hey test") is not None
        assert profile.resolve_alias("HEY TEST") is not None
