import asyncio
import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_connect_error(monkeypatch, state_module):
    class FailClient:
        def __init__(self, *args, **kwargs):
            self.host = kwargs["host"]
            self.connected = False

        def connect(self, callback=None):
            raise RuntimeError("boom")

    monkeypatch.setattr(state_module, "BambuClient", FailClient)
    with pytest.raises(HTTPException) as excinfo:
        await state_module._connect("p1")
    assert excinfo.value.status_code == 502
    _, errors = await state_module.state.snapshot()
    assert "p1" in errors
    assert "RuntimeError" in errors["p1"]


@pytest.mark.asyncio
async def test_connect_lock(monkeypatch, state_module):
    calls = 0

    class SlowClient:
        def __init__(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            self.host = kwargs["host"]
            self.connected = False

        def connect(self, callback=None):
            async def delayed():
                await asyncio.sleep(0.1)
                self.connected = True
            asyncio.create_task(delayed())

    monkeypatch.setattr(state_module, "BambuClient", SlowClient)

    c1, c2 = await asyncio.gather(
        state_module._connect("p1"),
        state_module._connect("p1"),
    )

    assert calls == 1
    assert c1 is c2
