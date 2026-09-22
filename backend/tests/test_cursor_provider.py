"""Cursor coach calls share one bridge and retry a slow startup once."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from app.services.ai import providers
from app.services.ai.base import ProviderError
from app.services.ai.providers import CursorProvider


class _Result:
    status = "finished"
    result = '{"reply": "ok"}'
    id = "run-1"
    usage = None


def _install_sdk(monkeypatch, prompt):
    client = SimpleNamespace(close=lambda: None)
    launches = {"count": 0}

    def launch_bridge(**kwargs):
        launches["count"] += 1
        launches["timeout"] = kwargs.get("timeout")
        return client

    sdk = SimpleNamespace(
        Agent=SimpleNamespace(prompt=prompt),
        AgentOptions=lambda **kwargs: kwargs,
        Client=SimpleNamespace(launch_bridge=launch_bridge),
        CursorAgentError=RuntimeError,
        LocalAgentOptions=lambda **kwargs: kwargs,
    )
    monkeypatch.setitem(sys.modules, "cursor_sdk", sdk)
    monkeypatch.setattr(providers, "_CURSOR_CLIENT", None)
    return launches


def test_two_calls_launch_the_bridge_once(monkeypatch):
    launches = _install_sdk(monkeypatch, lambda *args, **kwargs: _Result())
    provider = CursorProvider(model="composer-2.5", api_key="test-key")

    first = provider.generate_json("system", "user")
    second = provider.generate_json("system", "user")

    assert first.data["reply"] == "ok"
    assert second.data["reply"] == "ok"
    assert launches["count"] == 1
    assert launches["timeout"] == providers._BRIDGE_DISCOVERY_TIMEOUT_S


def test_discovery_timeout_retries_with_a_fresh_bridge(monkeypatch):
    calls = {"count": 0}

    def prompt(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("Timed out waiting for bridge discovery")
        return _Result()

    launches = _install_sdk(monkeypatch, prompt)
    provider = CursorProvider(model="composer-2.5", api_key="test-key")
    result = provider.generate_json("system", "user")

    assert result.data["reply"] == "ok"
    assert launches["count"] == 2


def test_second_discovery_timeout_is_a_provider_error(monkeypatch):
    def prompt(*args, **kwargs):
        raise RuntimeError("Timed out waiting for bridge discovery")

    _install_sdk(monkeypatch, prompt)
    provider = CursorProvider(model="composer-2.5", api_key="test-key")
    with pytest.raises(ProviderError, match="bridge discovery"):
        provider.generate_json("system", "user")
