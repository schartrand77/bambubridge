import pytest


def test_pairs(monkeypatch, bridge):
    monkeypatch.setenv("TEST_PAIRS", "a@1;b@2")
    assert bridge._pairs("TEST_PAIRS") == {"a": "1", "b": "2"}


def test_kv(monkeypatch, bridge):
    monkeypatch.setenv("TEST_KV", "a=1;b=2")
    assert bridge._kv("TEST_KV") == {"a": "1", "b": "2"}


def test_validate_env_missing(bridge, monkeypatch):
    monkeypatch.setattr(bridge, "PRINTERS", {"p1": "h"})
    monkeypatch.setattr(bridge, "SERIALS", {})
    monkeypatch.setattr(bridge, "LAN_KEYS", {"p1": "k"})
    with pytest.raises(RuntimeError):
        bridge._validate_env()
