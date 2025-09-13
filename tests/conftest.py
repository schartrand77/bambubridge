import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def cfg(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    monkeypatch.setenv("BAMBULAB_PRINTERS", "p1@127.0.0.1")
    monkeypatch.setenv("BAMBULAB_SERIALS", "p1=SERIAL1")
    monkeypatch.setenv("BAMBULAB_LAN_KEYS", "p1=LANKEY1")
    monkeypatch.setenv("BAMBULAB_TYPES", "p1=X1C")
    monkeypatch.setenv("BAMBULAB_API_KEY", "secret")
    import config
    importlib.reload(config)
    import asyncio
    asyncio.run(config._validate_env())
    return config


@pytest.fixture
def state_module(cfg):
    import state
    importlib.reload(state)
    return state


@pytest.fixture
def api_module(state_module):
    import api
    importlib.reload(api)
    return api


@pytest.fixture
def client(api_module, state_module, monkeypatch):
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

    monkeypatch.setattr(state_module, "BambuClient", FakeClient)
    with TestClient(api_module.app) as tc:
        yield tc
