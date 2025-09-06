import importlib
import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def bridge(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    monkeypatch.setenv("BAMBULAB_PRINTERS", "p1@127.0.0.1")
    monkeypatch.setenv("BAMBULAB_SERIALS", "p1=SERIAL1")
    monkeypatch.setenv("BAMBULAB_LAN_KEYS", "p1=LANKEY1")
    monkeypatch.setenv("BAMBULAB_TYPES", "p1=X1C")
    monkeypatch.setenv("BAMBULAB_API_KEY", "secret")
    import bridge as module
    importlib.reload(module)
    return module


@pytest.fixture
def client(bridge, monkeypatch):
    class FakeDev:
        get_version_data = {"firmware": "1.0"}
        push_all_data = {"state": "ok"}

    class FakeClient:
        def __init__(self, *, device_type, serial, host, local_mqtt, access_code, region, email, username, auth_token):
            self.device_type = device_type
            self.serial = serial
            self.host = host
            self.connected = False

        def connect(self, callback=None):
            self.connected = True

        def get_device(self):
            return FakeDev()

        def start_print_from_url(self, *, gcode_url, thmf_url=None):
            return {"started": gcode_url, "thmf": thmf_url}

        def pause_print(self):
            return {"paused": True}

        def resume_print(self):
            return {"resumed": True}

        def stop_print(self):
            return {"stopped": True}

        def camera_mjpeg(self):
            def gen():
                yield b"frame"
            return gen()

        def disconnect(self):
            self.connected = False

    monkeypatch.setattr(bridge, "BambuClient", FakeClient)
    with TestClient(bridge.app) as tc:
        yield tc
