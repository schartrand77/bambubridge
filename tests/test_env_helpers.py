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


def test_get_float(monkeypatch, cfg):
    monkeypatch.setenv("TEST_FLOAT", "1.5")
    assert cfg._get_float("TEST_FLOAT", "2") == 1.5


def test_get_float_fallback(monkeypatch, cfg, caplog):
    monkeypatch.setenv("TEST_FLOAT", "bad")
    with caplog.at_level(logging.ERROR):
        assert cfg._get_float("TEST_FLOAT", "2") == 2.0
    assert "Invalid TEST_FLOAT value" in caplog.text


def test_get_float_default_invalid(monkeypatch, cfg):
    monkeypatch.setenv("TEST_FLOAT", "bad")
    with pytest.raises(RuntimeError) as exc:
        cfg._get_float("TEST_FLOAT", "also-bad")
    assert "Invalid default for TEST_FLOAT" in str(exc.value)


def test_validate_env_missing(cfg, monkeypatch):
    monkeypatch.setattr(cfg, "PRINTERS", {"p1": "h"})
    monkeypatch.setattr(cfg, "SERIALS", {})
    monkeypatch.setattr(cfg, "LAN_KEYS", {"p1": "k"})
    with pytest.raises(RuntimeError) as exc:
        cfg._validate_env()
    assert "Missing BAMBULAB_SERIALS for p1" in str(exc.value)


def test_validate_env_multiple_missing(cfg, monkeypatch):
    monkeypatch.setattr(cfg, "PRINTERS", {"p1": "h"})
    monkeypatch.setattr(cfg, "SERIALS", {"p2": "s"})
    monkeypatch.setattr(cfg, "LAN_KEYS", {"p1": "k"})
    with pytest.raises(RuntimeError) as exc:
        cfg._validate_env()
    msg = str(exc.value)
    assert "Missing BAMBULAB_SERIALS for p1" in msg
    assert "Missing BAMBULAB_PRINTERS for p2" in msg
    assert "Missing BAMBULAB_LAN_KEYS for p2" in msg
