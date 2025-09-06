import logging
import pytest


def test_pairs(monkeypatch, cfg):
    monkeypatch.setenv("TEST_PAIRS", "a@1;b@2")
    assert cfg._pairs("TEST_PAIRS") == {"a": "1", "b": "2"}


def test_kv(monkeypatch, cfg):
    monkeypatch.setenv("TEST_KV", "a=1;b=2")
    assert cfg._kv("TEST_KV") == {"a": "1", "b": "2"}


def test_pairs_warn(monkeypatch, cfg, caplog):
    monkeypatch.setenv("TEST_PAIRS", "a@1;bad;b@2;oops")
    with caplog.at_level(logging.WARNING):
        assert cfg._pairs("TEST_PAIRS") == {"a": "1", "b": "2"}
    assert "bad" in caplog.text
    assert "oops" in caplog.text


def test_kv_warn(monkeypatch, cfg, caplog):
    monkeypatch.setenv("TEST_KV", "a=1;bad;b=2;oops")
    with caplog.at_level(logging.WARNING):
        assert cfg._kv("TEST_KV") == {"a": "1", "b": "2"}
    assert "bad" in caplog.text
    assert "oops" in caplog.text


def test_validate_env_missing(cfg, monkeypatch):
    monkeypatch.setattr(cfg, "PRINTERS", {"p1": "h"})
    monkeypatch.setattr(cfg, "SERIALS", {})
    monkeypatch.setattr(cfg, "LAN_KEYS", {"p1": "k"})
    with pytest.raises(RuntimeError):
        cfg._validate_env()
