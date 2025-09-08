"""Environment configuration for bambubridge.

Callers must not access configuration globals while revalidation is in
progress.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from threading import Lock
from types import MappingProxyType
from typing import Dict, Mapping, Iterator
from urllib.parse import urlparse

log = logging.getLogger("bambubridge")


def _parse_env(env: str, sep: str, err: str, sep_char: str) -> Dict[str, str]:
    """Parse ``key{sep}value`` pairs from ``env`` separated by ``sep_char``.

    ``err`` is a format string used when an invalid segment is encountered.
    """

    out: Dict[str, str] = {}
    seen: set[str] = set()
    raw = os.getenv(env, "")
    for part in filter(None, raw.split(sep_char)):
        if sep in part:
            k, v = part.split(sep, 1)
            key = k.strip()
            if key in seen:
                raise ValueError(f"Duplicate {env} entry for '{key}'")
            seen.add(key)
            out[key] = v.strip()
        else:
            log.warning(err, part)
    return out


def _pairs(env: str, sep_char: str = ";") -> Dict[str, str]:
    """Parse ``name@host`` segments into dicts using ``sep_char`` as delimiter."""

    return _parse_env(env, "@", "Invalid printer pair segment '%s'", sep_char)


def _kv(env: str, sep_char: str = ";") -> Dict[str, str]:
    """Parse ``key=value`` segments into dicts using ``sep_char`` as delimiter."""

    return _parse_env(env, "=", "Invalid key/value segment '%s'", sep_char)


def _get_float(env: str, default: str) -> float:
    """Return a float from ``env`` or ``default`` with error handling."""
    try:
        default_val: float = float(default)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid default for {env}: {default}"
        ) from exc

    raw = os.getenv(env)
    if raw is None:
        return default_val
    try:
        return float(raw)
    except ValueError:
        log.error("Invalid %s value %r; using default %s", env, raw, default)
        return default_val


_PRINTERS: Dict[str, str] = {}
_SERIALS: Dict[str, str] = {}
_LAN_KEYS: Dict[str, str] = {}
_TYPES: Dict[str, str] = {}

PRINTERS: Mapping[str, str] = MappingProxyType(_PRINTERS)
SERIALS: Mapping[str, str] = MappingProxyType(_SERIALS)
LAN_KEYS: Mapping[str, str] = MappingProxyType(_LAN_KEYS)
TYPES: Mapping[str, str] = MappingProxyType(_TYPES)

_CONFIG_LOCK = Lock()


@contextmanager
def read_lock() -> Iterator[None]:
    """Acquire the configuration lock for safe concurrent reads."""
    with _CONFIG_LOCK:
        yield

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


def _load_allow_origins() -> list[str]:
    """Return a validated list of CORS origins from ``BAMBULAB_ALLOW_ORIGINS``."""

    raw = [
        o.strip()
        for o in os.getenv("BAMBULAB_ALLOW_ORIGINS", "").split(",")
        if o.strip()
    ]
    origins: list[str] = []
    for origin in raw:
        parsed = urlparse(origin)
        if (
            parsed.scheme in {"http", "https"}
            and parsed.netloc
            and not parsed.params
            and not parsed.query
            and not parsed.fragment
        ):
            origins.append(origin)
        else:
            log.warning("Ignoring invalid origin '%s'", origin)
    return list(dict.fromkeys(origins or DEFAULT_ORIGINS))


ALLOW_ORIGINS = _load_allow_origins()
API_KEY = os.getenv("BAMBULAB_API_KEY")


def _validate_env() -> None:
    """Cross-check name sets and ensure required fields exist.

    Callers must not access configuration globals while revalidation is in
    progress.
    """

    global API_KEY, ALLOW_ORIGINS

    try:
        printers = _pairs("BAMBULAB_PRINTERS")
        serials = _kv("BAMBULAB_SERIALS")
        lan_keys = _kv("BAMBULAB_LAN_KEYS")
        types = _kv("BAMBULAB_TYPES")
    except ValueError as exc:
        raise RuntimeError(f"Printer configuration invalid: {exc}") from exc

    with _CONFIG_LOCK:
        _PRINTERS.clear()
        _PRINTERS.update(printers)
        _SERIALS.clear()
        _SERIALS.update(serials)
        _LAN_KEYS.clear()
        _LAN_KEYS.update(lan_keys)
        _TYPES.clear()
        _TYPES.update(types)
        API_KEY = os.getenv("BAMBULAB_API_KEY")
        ALLOW_ORIGINS = _load_allow_origins()

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


def _mutable_copy(mapping: Mapping[str, str]) -> Dict[str, str]:
    """Return a mutable copy of a configuration mapping.

    Tests can use this to obtain a dict that may be modified without affecting
    the global read-only configuration views.
    """

    return dict(mapping)
