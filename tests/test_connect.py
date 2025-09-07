import asyncio
import time
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
            time.sleep(0.1)
            self.connected = True

    monkeypatch.setattr(state_module, "BambuClient", SlowClient)

    c1, c2 = await asyncio.gather(
        state_module._connect("p1"),
        state_module._connect("p1"),
    )

    assert calls == 1
    assert c1 is c2


@pytest.mark.asyncio
async def test_connect_coroutine(monkeypatch, state_module):
    called = False

    class AsyncClient:
        def __init__(self, *args, **kwargs):
            self.host = kwargs["host"]
            self.connected = False

        async def connect(self, callback=None):
            nonlocal called
            called = True
            self.connected = True

    async def fail_to_thread(*args, **kwargs):
        raise AssertionError("to_thread should not be called")

    monkeypatch.setattr(state_module, "BambuClient", AsyncClient)
    monkeypatch.setattr(state_module.asyncio, "to_thread", fail_to_thread)

    c = await state_module._connect("p1")
    assert called is True
    assert c.connected is True


@pytest.mark.asyncio
async def test_connect_without_callback(monkeypatch, state_module):
    class NoCallbackClient:
        def __init__(self, *args, **kwargs):
            self.host = kwargs["host"]
            self.connected = False

        def connect(self):
            self.connected = True

    monkeypatch.setattr(state_module, "BambuClient", NoCallbackClient)

    c = await state_module._connect("p1")
    assert c.connected is True


@pytest.mark.asyncio
async def test_connect_timeout_configurable(monkeypatch, state_module):
    class NeverClient:
        def __init__(self, *args, **kwargs):
            self.host = kwargs["host"]
            self.connected = False

        def connect(self, callback=None):
            pass

    monkeypatch.setattr(state_module, "BambuClient", NeverClient)

    with pytest.raises(RuntimeError):
        await state_module._connect(
            "p1", raise_http=False, wait_interval=0.01, max_wait=0.02
        )


@pytest.mark.asyncio
async def test_connect_closes_old_client(monkeypatch, state_module):
    await state_module.state.clear()

    class OldClient:
        def __init__(self):
            self.connected = False
            self.closed = False

        def close(self):
            self.closed = True

    class NewClient:
        def __init__(self, *args, **kwargs):
            self.host = kwargs["host"]
            self.connected = False

        def connect(self, callback=None):
            self.connected = True

    old = OldClient()
    await state_module.state.set_client("p1", old)
    monkeypatch.setattr(state_module, "BambuClient", NewClient)

    new = await state_module._connect("p1")
    assert old.closed is True
    assert new is not old
    assert await state_module.state.get_client("p1") is new
