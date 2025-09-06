"""Printer connection state and helpers for bambubridge."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

from fastapi import HTTPException

from config import (
    PRINTERS,
    SERIALS,
    LAN_KEYS,
    TYPES,
    REGION,
    EMAIL,
    USERNAME,
    AUTH_TOKEN,
)

log = logging.getLogger("bambubridge")

try:
    from pybambu import BambuClient  # 1.0.x
except Exception as e:  # pragma: no cover - dependency error
    raise RuntimeError(f"Failed to import pybambu: {e}")


class PrinterState:
    """Holds printer connection state with concurrency guards."""

    def __init__(self) -> None:
        self.clients: Dict[str, BambuClient] = {}
        self.last_error: Dict[str, str] = {}
        self.lock = asyncio.Lock()

    async def get_client(self, name: str) -> Optional[BambuClient]:
        async with self.lock:
            return self.clients.get(name)

    async def set_client(self, name: str, client: BambuClient) -> None:
        async with self.lock:
            self.clients[name] = client
            self.last_error.pop(name, None)

    async def set_error(self, name: str, detail: str) -> None:
        async with self.lock:
            self.last_error[name] = detail

    async def snapshot(self) -> tuple[Dict[str, BambuClient], Dict[str, str]]:
        async with self.lock:
            return dict(self.clients), dict(self.last_error)

    async def clear(self) -> None:
        async with self.lock:
            self.clients.clear()
            self.last_error.clear()


state = PrinterState()


def _require_known(name: str) -> None:
    if name not in PRINTERS:
        raise HTTPException(404, f"Unknown printer '{name}'")
    if name not in SERIALS:
        raise HTTPException(400, f"Missing serial for '{name}' (set BAMBULAB_SERIALS)")
    if name not in LAN_KEYS:
        raise HTTPException(400, f"Missing access code for '{name}' (set BAMBULAB_LAN_KEYS)")


async def _connect(name: str, raise_http: bool = True) -> BambuClient:
    """Ensure a connected BambuClient; return it or raise HTTP error."""
    _require_known(name)

    c = await state.get_client(name)
    if c and getattr(c, "connected", False):
        return c

    host = PRINTERS[name]
    serial = SERIALS[name]
    access = LAN_KEYS[name]
    dtype = TYPES.get(name, "X1C")

    try:
        c = BambuClient(
            device_type=dtype,
            serial=serial,
            host=host,
            local_mqtt=True,
            access_code=access,
            region=REGION,
            email=EMAIL,
            username=USERNAME,
            auth_token=AUTH_TOKEN,
        )
        c.connect(callback=lambda evt: None)

        for _ in range(50):
            if c.connected:
                break
            await asyncio.sleep(0.1)

        if not c.connected:
            raise RuntimeError("Printer MQTT connected=False after wait")

        await state.set_client(name, c)
        log.info("connected: %s@%s (%s)", name, host, serial)
        return c

    except Exception as e:  # pragma: no cover - network failures
        detail = f"{type(e).__name__}: {e}"
        await state.set_error(name, detail)
        log.warning("connect(%s) failed: %s", name, detail)
        if raise_http:
            raise HTTPException(status_code=502, detail=f"connect failed: {detail}")
        raise
