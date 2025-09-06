import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from state import _RLock


@pytest.mark.asyncio
async def test_rlock_acquire_without_task(monkeypatch):
    lock = _RLock()
    monkeypatch.setattr(asyncio, "current_task", lambda loop=None: None)
    with pytest.raises(RuntimeError, match="RLock used outside running event loop"):
        await lock.acquire()


def test_rlock_release_without_task(monkeypatch):
    lock = _RLock()
    monkeypatch.setattr(asyncio, "current_task", lambda loop=None: None)
    with pytest.raises(RuntimeError, match="RLock used outside running event loop"):
        lock.release()
