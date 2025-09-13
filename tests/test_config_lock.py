import asyncio

import pytest


@pytest.mark.asyncio
async def test_concurrent_async_reads(cfg):
    async def reader():
        async with cfg.read_lock():
            await asyncio.sleep(0)

    await asyncio.wait_for(
        asyncio.gather(*(reader() for _ in range(5))),
        timeout=1,
    )
