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
