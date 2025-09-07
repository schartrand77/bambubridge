import asyncio

import pytest


@pytest.mark.asyncio
async def test_rwlock_allows_concurrent_reads_and_blocks_writes(state_module):
    ps = state_module.PrinterState()
    release = asyncio.Event()
    active: list[int] = []

    async def reader():
        async with ps.read_lock():
            active.append(1)
            await release.wait()

    r1 = asyncio.create_task(reader())
    r2 = asyncio.create_task(reader())
    await asyncio.sleep(0.1)
    assert len(active) == 2

    writer_started = asyncio.Event()
    writer_acquired = asyncio.Event()

    async def writer():
        writer_started.set()
        async with ps.write_lock:
            writer_acquired.set()

    w = asyncio.create_task(writer())
    await writer_started.wait()
    await asyncio.sleep(0.1)
    assert not writer_acquired.is_set()

    release.set()
    await asyncio.wait_for(writer_acquired.wait(), timeout=1)
    await asyncio.gather(r1, r2, w)


@pytest.mark.asyncio
async def test_rwlock_cancellation_safe(state_module):
    ps = state_module.PrinterState()

    async def reader():
        async with ps.read_lock():
            await asyncio.sleep(1)

    t = asyncio.create_task(reader())
    await asyncio.sleep(0.1)
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t

    await asyncio.wait_for(ps.write_lock.acquire(), timeout=1)
    ps.write_lock.release()
