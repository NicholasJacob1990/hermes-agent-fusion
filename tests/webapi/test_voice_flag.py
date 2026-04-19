"""HERMES_VOICE_BROWSER_ENABLED feature flag — default OFF, accepts truthy values."""

from __future__ import annotations

import pytest

from webapi.deps import is_voice_browser_enabled


def test_voice_browser_disabled_by_default(monkeypatch):
    monkeypatch.delenv("HERMES_VOICE_BROWSER_ENABLED", raising=False)
    assert is_voice_browser_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_voice_browser_enabled_from_truthy_env(monkeypatch, value):
    monkeypatch.setenv("HERMES_VOICE_BROWSER_ENABLED", value)
    assert is_voice_browser_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "enabled-maybe"])
def test_voice_browser_disabled_for_non_truthy_env(monkeypatch, value):
    monkeypatch.setenv("HERMES_VOICE_BROWSER_ENABLED", value)
    assert is_voice_browser_enabled() is False
