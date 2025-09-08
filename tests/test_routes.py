def test_health_and_printers(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"]["printers"] == ["p1"]

    res = client.get("/api/printers")
    assert res.status_code == 200
    data = res.json()
    printer = data[0]
    assert printer["name"] == "p1"
    assert printer["host"] == "127.0.0.1"
    assert printer["serial"] == "SERIAL1"
    assert printer["connected"] is False
    assert printer["last_error"] is None


def test_unknown_status_returns_404(client):
    res = client.get("/api/unknown/status")
    assert res.status_code == 404


def test_status_before_connection(client):
    res = client.get("/api/p1/status")
    assert res.status_code == 200
    data = res.json()["status"]
    assert data["name"] == "p1"
    assert data["host"] == "127.0.0.1"
    assert data["serial"] == "SERIAL1"
    assert data["connected"] is True
    assert data["get_version"] == {"firmware": "1.0"}
    assert data["push_all"] == {"state": "ok"}


def test_connect_status_and_actions(client):
    headers = {"X-API-Key": "secret"}

    res = client.post("/api/p1/connect", headers=headers)
    assert res.status_code == 200
    assert res.json()["ok"] is True

    res = client.get("/api/p1/status")
    assert res.status_code == 200
    assert res.json()["status"]["connected"] is True

    res = client.post(
        "/api/p1/print",
        json={"gcode_url": "http://example.com/file.gcode"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["result"]["started"] == "http://example.com/file.gcode"

    assert (
        client.post("/api/p1/pause", headers=headers).json()["result"]["paused"]
        is True
    )
    assert (
        client.post("/api/p1/resume", headers=headers).json()["result"]["resumed"]
        is True
    )
    assert (
        client.post("/api/p1/stop", headers=headers).json()["result"]["stopped"]
        is True
    )


def test_protected_route_requires_key(client):
    res = client.post("/api/p1/connect")
    assert res.status_code == 401


def test_disconnect(client):
    headers = {"X-API-Key": "secret"}

    assert client.post("/api/p1/connect", headers=headers).status_code == 200
    res = client.post("/api/p1/disconnect", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["result"]["name"] == "p1"

    data = client.get("/api/printers").json()
    printer = data[0]
    assert printer["connected"] is False
    assert printer["host"] == "127.0.0.1"
    assert printer["serial"] == "SERIAL1"
    assert printer["last_error"] is None

    res = client.post("/api/p1/disconnect", headers=headers)
    assert res.status_code == 404
