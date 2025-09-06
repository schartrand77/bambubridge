import asyncio

import pytest


@pytest.mark.asyncio
async def test_lock_not_reentrant():
    lock = asyncio.Lock()
    await lock.acquire()
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(lock.acquire(), timeout=0.1)
    lock.release()


def test_release_without_acquire():
    lock = asyncio.Lock()
    with pytest.raises(RuntimeError):
        lock.release()
