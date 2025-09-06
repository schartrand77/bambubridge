def test_health_and_printers(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"]["printers"] == ["p1"]

    res = client.get("/api/printers")
    assert res.status_code == 200
    data = res.json()
    assert data[0]["name"] == "p1"
    assert data[0]["connected"] is False


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
    assert res.status_code == 403


def test_disconnect(client):
    headers = {"X-API-Key": "secret"}

    assert client.post("/api/p1/connect", headers=headers).status_code == 200
    res = client.post("/api/p1/disconnect", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["result"]["name"] == "p1"

    data = client.get("/api/printers").json()
    assert data[0]["connected"] is False

    res = client.post("/api/p1/disconnect", headers=headers)
    assert res.status_code == 404
