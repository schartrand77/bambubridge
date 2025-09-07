import importlib
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


def test_startup_requires_api_key(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    monkeypatch.delenv("BAMBULAB_API_KEY", raising=False)
    monkeypatch.setenv("BAMBULAB_PRINTERS", "p1@127.0.0.1")
    monkeypatch.setenv("BAMBULAB_SERIALS", "p1=SERIAL1")
    monkeypatch.setenv("BAMBULAB_LAN_KEYS", "p1=LANKEY1")
    monkeypatch.setenv("BAMBULAB_TYPES", "p1=X1C")
    import config
    importlib.reload(config)
    import state
    importlib.reload(state)
    import api
    importlib.reload(api)

    with pytest.raises(RuntimeError) as excinfo:
        with TestClient(api.app):
            pass
    assert str(excinfo.value) == "API key not configured"


@pytest.mark.asyncio
async def test_dependency_requires_configured_api_key(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    monkeypatch.delenv("BAMBULAB_API_KEY", raising=False)
    monkeypatch.setenv("BAMBULAB_PRINTERS", "p1@127.0.0.1")
    monkeypatch.setenv("BAMBULAB_SERIALS", "p1=SERIAL1")
    monkeypatch.setenv("BAMBULAB_LAN_KEYS", "p1=LANKEY1")
    monkeypatch.setenv("BAMBULAB_TYPES", "p1=X1C")
    import config
    importlib.reload(config)
    import api
    importlib.reload(api)

    with pytest.raises(HTTPException) as excinfo:
        await api.require_api_key(api_key="test")
    assert excinfo.value.status_code == 500

