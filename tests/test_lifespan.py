import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

import pytest


@pytest.fixture
def bridge_autoconnect(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    monkeypatch.setenv("BAMBULAB_PRINTERS", "p1@127.0.0.1")
    monkeypatch.setenv("BAMBULAB_SERIALS", "p1=SERIAL1")
    monkeypatch.setenv("BAMBULAB_LAN_KEYS", "p1=LANKEY1")
    monkeypatch.setenv("BAMBULAB_TYPES", "p1=X1C")
    monkeypatch.setenv("BAMBULAB_AUTOCONNECT", "1")
    import bridge as module
    importlib.reload(module)
    return module


def test_autoconnect_and_shutdown(monkeypatch, bridge_autoconnect):
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

    monkeypatch.setattr(bridge_autoconnect, "BambuClient", FakeClient)

    with TestClient(bridge_autoconnect.app):
        assert "p1" in bridge_autoconnect.state.clients
        assert bridge_autoconnect.state.clients["p1"].connected is True

    assert bridge_autoconnect.state.clients == {}
    assert len(disconnected) == 1
