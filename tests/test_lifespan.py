import importlib
from pathlib import Path

from fastapi.testclient import TestClient

import pytest


@pytest.fixture
def api_autoconnect(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent.parent))
    monkeypatch.setenv("BAMBULAB_PRINTERS", "p1@127.0.0.1")
    monkeypatch.setenv("BAMBULAB_SERIALS", "p1=SERIAL1")
    monkeypatch.setenv("BAMBULAB_LAN_KEYS", "p1=LANKEY1")
    monkeypatch.setenv("BAMBULAB_TYPES", "p1=X1C")
    monkeypatch.setenv("BAMBULAB_AUTOCONNECT", "1")
    monkeypatch.setenv("BAMBULAB_API_KEY", "secret")
    import config
    import state
    import api
    importlib.reload(config)
    config._validate_env()
    importlib.reload(state)
    importlib.reload(api)
    return state, api


def test_autoconnect_and_shutdown(monkeypatch, api_autoconnect):
    state, api = api_autoconnect
    disconnected = []

    class FakeClient:
        def __init__(self, *, device_type, serial, host, local_mqtt, access_code, region, email, username, auth_token):
            self.host = host
            self.connected = False

        def connect(self, callback=None):
            self.connected = True

        def disconnect(self):
            self.connected = False
            disconnected.append(self.host)

    monkeypatch.setattr(state, "BambuClient", FakeClient)

    with TestClient(api.app):
        assert "p1" in state.state.clients
        assert state.state.clients["p1"].connected is True

    assert state.state.clients == {}
    assert len(disconnected) == 1
