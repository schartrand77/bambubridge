def test_camera_stream(client, monkeypatch):
    from state import BambuClient

    chunks = [b"chunk1", b"chunk2"]

    def fake_camera_mjpeg(self):
        def gen():
            for c in chunks:
                yield c
        return gen()

    monkeypatch.setattr(BambuClient, "camera_mjpeg", fake_camera_mjpeg)

    headers = {"X-API-Key": "secret"}
    with client.stream("GET", "/api/p1/camera", headers=headers) as res:
        assert res.status_code == 200
        data = list(res.iter_bytes())
    assert b"".join(data) == b"".join(chunks)
