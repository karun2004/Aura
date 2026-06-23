"""Tests for the safety/confirmation layer."""

from aura.safety.classifier import SafetyClassifier, RiskLevel


def test_destructive_actions_classified_correctly():
    classifier = SafetyClassifier()
    assert classifier.classify("delete") == RiskLevel.DESTRUCTIVE
    assert classifier.classify("overwrite") == RiskLevel.DESTRUCTIVE
    assert classifier.classify("send_email") == RiskLevel.DESTRUCTIVE


def test_safe_actions_classified_correctly():
    classifier = SafetyClassifier()
    assert classifier.classify("read_content") == RiskLevel.SAFE
    assert classifier.classify("list_tabs") == RiskLevel.SAFE
    assert classifier.classify("navigate") == RiskLevel.SAFE


def test_destructive_requires_confirmation():
    classifier = SafetyClassifier()
    assert classifier.requires_confirmation(RiskLevel.DESTRUCTIVE) is True
    assert classifier.requires_confirmation(RiskLevel.SAFE) is False


def test_multi_item_delete_requires_double_confirmation():
    classifier = SafetyClassifier()
    assert classifier.requires_double_confirmation("delete", {"count": 5}) is True
    assert classifier.requires_double_confirmation("delete", {"count": 1}) is False
