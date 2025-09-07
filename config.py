"""Environment configuration for bambubridge."""

from __future__ import annotations

import os
import logging
from typing import Dict

log = logging.getLogger("bambubridge")


def _pairs(env: str) -> Dict[str, str]:
    """Parse "name@host;other@host2" strings into dicts."""
    out: Dict[str, str] = {}
    seen: set[str] = set()
    raw = os.getenv(env, "")
    for part in filter(None, raw.split(";")):
        if "@" in part:
            n, h = part.split("@", 1)
            key = n.strip()
            if key in seen:
                raise ValueError(f"Duplicate {env} entry for '{key}'")
            seen.add(key)
            out[key] = h.strip()
        else:
            log.warning("Invalid printer pair segment '%s'", part)
    return out


def _kv(env: str) -> Dict[str, str]:
    """Parse "key=value;other=value2" strings into dicts."""
    out: Dict[str, str] = {}
    seen: set[str] = set()
    raw = os.getenv(env, "")
    for part in filter(None, raw.split(";")):
        if "=" in part:
            k, v = part.split("=", 1)
            key = k.strip()
            if key in seen:
                raise ValueError(f"Duplicate {env} entry for '{key}'")
            seen.add(key)
            out[key] = v.strip()
        else:
            log.warning("Invalid key/value segment '%s'", part)
    return out


def _get_float(env: str, default: str) -> float:
    """Return a float from ``env`` or ``default`` with error handling."""
    raw = os.getenv(env, default)
    try:
        return float(raw)
    except ValueError:
        log.error("Invalid %s value %r; using default %s", env, raw, default)
        try:
            return float(default)
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid default for {env}: {default}"
            ) from exc


PRINTERS: Dict[str, str] = {}
SERIALS: Dict[str, str] = {}
LAN_KEYS: Dict[str, str] = {}
TYPES: Dict[str, str] = {}

REGION = os.getenv("BAMBULAB_REGION", "US")
EMAIL = os.getenv("BAMBULAB_EMAIL", "")
USERNAME = os.getenv("BAMBULAB_USERNAME", "")
AUTH_TOKEN = os.getenv("BAMBULAB_AUTH_TOKEN", "")
AUTOCONNECT = os.getenv("BAMBULAB_AUTOCONNECT", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

CONNECT_INTERVAL = _get_float("BAMBULAB_CONNECT_INTERVAL", "0.1")
CONNECT_TIMEOUT = _get_float("BAMBULAB_CONNECT_TIMEOUT", "5")

DEFAULT_ORIGINS = ["http://localhost", "http://127.0.0.1"]
ALLOW_ORIGINS = [
    o.strip() for o in os.getenv("BAMBULAB_ALLOW_ORIGINS", "").split(",") if o.strip()
] or DEFAULT_ORIGINS

API_KEY = os.getenv("BAMBULAB_API_KEY")


def _validate_env() -> None:
    """Cross-check name sets and ensure required fields exist."""
    try:
        printers = _pairs("BAMBULAB_PRINTERS")
        serials = _kv("BAMBULAB_SERIALS")
        lan_keys = _kv("BAMBULAB_LAN_KEYS")
        types = _kv("BAMBULAB_TYPES")
    except ValueError as exc:
        raise RuntimeError(f"Printer configuration invalid: {exc}") from exc

    PRINTERS.clear()
    PRINTERS.update(printers)
    SERIALS.clear()
    SERIALS.update(serials)
    LAN_KEYS.clear()
    LAN_KEYS.update(lan_keys)
    TYPES.clear()
    TYPES.update(types)

    names = set(PRINTERS) | set(SERIALS) | set(LAN_KEYS) | set(TYPES)
    missing_required: list[tuple[str, str]] = []
    for n in names:
        if n not in PRINTERS:
            missing_required.append((n, "BAMBULAB_PRINTERS"))
        if n not in SERIALS:
            missing_required.append((n, "BAMBULAB_SERIALS"))
        if n not in LAN_KEYS:
            missing_required.append((n, "BAMBULAB_LAN_KEYS"))
        if n not in TYPES:
            log.warning("Missing BAMBULAB_TYPES for '%s'; defaulting to X1C", n)
    if missing_required:
        for name, env in missing_required:
            log.error("Missing %s entry for '%s'", env, name)
        details = "; ".join(
            f"Missing {env} for {name}" for name, env in missing_required
        )
        raise RuntimeError(f"Printer configuration incomplete: {details}")
