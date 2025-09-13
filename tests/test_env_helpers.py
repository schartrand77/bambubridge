import asyncio
import logging
from types import MappingProxyType

import pytest


def test_pairs(monkeypatch, cfg):
    monkeypatch.setenv("TEST_PAIRS", "a@1;b@2")
    assert cfg._pairs("TEST_PAIRS") == {"a": "1", "b": "2"}


def test_kv(monkeypatch, cfg):
    monkeypatch.setenv("TEST_KV", "a=1;b=2")
    assert cfg._kv("TEST_KV") == {"a": "1", "b": "2"}


def test_pairs_custom_separator(monkeypatch, cfg):
    monkeypatch.setenv("TEST_PAIRS_CUSTOM", "a@1|b@2")
    assert cfg._pairs("TEST_PAIRS_CUSTOM", sep_char="|") == {
        "a": "1",
        "b": "2",
    }


def test_kv_custom_separator(monkeypatch, cfg):
    monkeypatch.setenv("TEST_KV_CUSTOM", "a=1|b=2")
    assert cfg._kv("TEST_KV_CUSTOM", sep_char="|") == {"a": "1", "b": "2"}


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


def test_pairs_duplicate_error(monkeypatch, cfg):
    monkeypatch.setenv("TEST_DUP_PAIRS", "a@1;a@2")
    with pytest.raises(ValueError) as exc:
        cfg._pairs("TEST_DUP_PAIRS")
    assert "Duplicate TEST_DUP_PAIRS entry for 'a'" in str(exc.value)


def test_kv_duplicate_error(monkeypatch, cfg):
    monkeypatch.setenv("TEST_DUP_KV", "a=1;a=2")
    with pytest.raises(ValueError) as exc:
        cfg._kv("TEST_DUP_KV")
    assert "Duplicate TEST_DUP_KV entry for 'a'" in str(exc.value)


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
    monkeypatch.setenv("BAMBULAB_PRINTERS", "p1@h")
    monkeypatch.setenv("BAMBULAB_SERIALS", "")
    monkeypatch.setenv("BAMBULAB_LAN_KEYS", "p1=k")
    monkeypatch.setenv("BAMBULAB_TYPES", "p1=X1C")
    with pytest.raises(RuntimeError) as exc:
        asyncio.run(cfg._validate_env())
    assert "Missing BAMBULAB_SERIALS for p1" in str(exc.value)


def test_validate_env_multiple_missing(cfg, monkeypatch):
    monkeypatch.setenv("BAMBULAB_PRINTERS", "p1@h")
    monkeypatch.setenv("BAMBULAB_SERIALS", "p2=s")
    monkeypatch.setenv("BAMBULAB_LAN_KEYS", "p1=k")
    monkeypatch.setenv("BAMBULAB_TYPES", "")
    with pytest.raises(RuntimeError) as exc:
        asyncio.run(cfg._validate_env())
    msg = str(exc.value)
    assert "Missing BAMBULAB_SERIALS for p1" in msg
    assert "Missing BAMBULAB_PRINTERS for p2" in msg
    assert "Missing BAMBULAB_LAN_KEYS for p2" in msg


def test_validate_env_duplicate(cfg, monkeypatch):
    monkeypatch.setenv("BAMBULAB_PRINTERS", "a@1;a@2")
    monkeypatch.setenv("BAMBULAB_SERIALS", "a=s")
    monkeypatch.setenv("BAMBULAB_LAN_KEYS", "a=k")
    monkeypatch.setenv("BAMBULAB_TYPES", "a=X1C")
    with pytest.raises(RuntimeError) as exc:
        asyncio.run(cfg._validate_env())
    assert "Duplicate BAMBULAB_PRINTERS entry for 'a'" in str(exc.value)


def test_allow_origins_validation(monkeypatch, caplog, cfg):
    monkeypatch.setenv(
        "BAMBULAB_ALLOW_ORIGINS",
        "http://good.com,not-a-url,https://ok.org,ftp://bad.com,http://good.com,https://ok.org",
    )
    with caplog.at_level(logging.WARNING):
        asyncio.run(cfg._validate_env())

    assert cfg.ALLOW_ORIGINS == ["http://good.com", "https://ok.org"]
    assert "Ignoring invalid origin 'not-a-url'" in caplog.text
    assert "Ignoring invalid origin 'ftp://bad.com'" in caplog.text


def test_validate_env_rereads_api_key_and_origins(monkeypatch, cfg):
    monkeypatch.setenv("BAMBULAB_API_KEY", "first")
    monkeypatch.setenv("BAMBULAB_ALLOW_ORIGINS", "http://one.com")
    asyncio.run(cfg._validate_env())
    assert cfg.API_KEY == "first"
    assert cfg.ALLOW_ORIGINS == ["http://one.com"]

    monkeypatch.setenv("BAMBULAB_API_KEY", "second")
    monkeypatch.setenv("BAMBULAB_ALLOW_ORIGINS", "http://two.com")
    asyncio.run(cfg._validate_env())
    assert cfg.API_KEY == "second"
    assert cfg.ALLOW_ORIGINS == ["http://two.com"]


def test_config_readonly_and_copy(monkeypatch, cfg):
    monkeypatch.setenv("BAMBULAB_PRINTERS", "p1@h")
    monkeypatch.setenv("BAMBULAB_SERIALS", "p1=s")
    monkeypatch.setenv("BAMBULAB_LAN_KEYS", "p1=k")
    monkeypatch.setenv("BAMBULAB_TYPES", "p1=X1C")
    asyncio.run(cfg._validate_env())

    assert isinstance(cfg.PRINTERS, MappingProxyType)

    with pytest.raises(TypeError):
        cfg.PRINTERS["p2"] = "h2"  # type: ignore[index]

    mutable = cfg._mutable_copy(cfg.PRINTERS)
    mutable["p2"] = "h2"
    assert "p2" not in cfg.PRINTERS


def test_connect_interval_invalid(monkeypatch, caplog):
    monkeypatch.setenv("BAMBULAB_CONNECT_INTERVAL", "0")
    import sys
    sys.modules.pop("config", None)
    with caplog.at_level(logging.ERROR):
        import config as cfg  # type: ignore[import]
    assert cfg.CONNECT_INTERVAL == 0.1
    assert "BAMBULAB_CONNECT_INTERVAL must be > 0" in caplog.text


def test_connect_timeout_invalid(monkeypatch, caplog):
    monkeypatch.setenv("BAMBULAB_CONNECT_TIMEOUT", "-1")
    import sys
    sys.modules.pop("config", None)
    with caplog.at_level(logging.ERROR):
        import config as cfg  # type: ignore[import]
    assert cfg.CONNECT_TIMEOUT == 5
    assert "BAMBULAB_CONNECT_TIMEOUT must be > 0" in caplog.text
