"""Utility helpers for bambubridge."""

from __future__ import annotations

from typing import Any, Callable, Optional


def _pick(obj: Any, names: tuple[str, ...]) -> Optional[Callable]:
    """Return the first callable attribute found on *obj* matching *names*."""
    for n in names:
        fn = getattr(obj, n, None)
        if callable(fn):
            return fn
    return None

