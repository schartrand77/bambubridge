import pytest


@pytest.mark.parametrize("impl", ["sync", "async", "callable", "generator"])
def test_camera_stream(client, monkeypatch, impl):
    from state import BambuClient

    chunks = [b"chunk1", b"chunk2"]

    if impl == "async":
        async def fake_camera_mjpeg(self):
            async def gen():
                for c in chunks:
                    yield c
            return gen()

        monkeypatch.setattr(BambuClient, "camera_mjpeg", fake_camera_mjpeg)
    elif impl == "sync":
        def fake_camera_mjpeg(self):
            def gen():
                for c in chunks:
                    yield c
            return gen()

        monkeypatch.setattr(BambuClient, "camera_mjpeg", fake_camera_mjpeg)
    elif impl == "generator":
        def gen():
            for c in chunks:
                yield c
        monkeypatch.setattr(BambuClient, "camera_mjpeg", gen())
    else:
        class FakeCameraMjpeg:
            def __call__(self):
                def gen():
                    for c in chunks:
                        yield c
                return gen()

        monkeypatch.setattr(BambuClient, "camera_mjpeg", FakeCameraMjpeg())

    headers = {"X-API-Key": "secret"}
    with client.stream("GET", "/api/p1/camera", headers=headers) as res:
        assert res.status_code == 200
        data = list(res.iter_bytes())
    assert b"".join(data) == b"".join(chunks)


@pytest.mark.parametrize("impl", ["sync", "async"])
def test_camera_stream_closes(client, monkeypatch, impl):
    """Ensure camera generators are properly closed when streaming ends."""
    from state import BambuClient

    closed = False
    chunks = [b"c1", b"c2"]

    if impl == "async":
        async def fake_camera_mjpeg(self):
            async def gen():
                nonlocal closed
                try:
                    for c in chunks:
                        yield c
                finally:
                    closed = True

            return gen()

        monkeypatch.setattr(BambuClient, "camera_mjpeg", fake_camera_mjpeg)
    else:
        def fake_camera_mjpeg(self):
            def gen():
                nonlocal closed
                try:
                    for c in chunks:
                        yield c
                finally:
                    closed = True

            return gen()

        monkeypatch.setattr(BambuClient, "camera_mjpeg", fake_camera_mjpeg)

    headers = {"X-API-Key": "secret"}
    with client.stream("GET", "/api/p1/camera", headers=headers) as res:
        assert res.status_code == 200
        it = res.iter_bytes()
        next(it)
    assert closed


@pytest.mark.parametrize("impl", ["sync", "async"])
def test_camera_stream_bad_chunk(client, monkeypatch, impl):
    """Non-byte chunks should trigger an error and close the generator."""
    from state import BambuClient

    closed = False

    if impl == "async":
        async def fake_camera_mjpeg(self):
            async def gen():
                nonlocal closed
                try:
                    yield b"good"
                    yield "bad"
                finally:
                    closed = True

            return gen()

        monkeypatch.setattr(BambuClient, "camera_mjpeg", fake_camera_mjpeg)
    else:
        def fake_camera_mjpeg(self):
            def gen():
                nonlocal closed
                try:
                    yield b"good"
                    yield "bad"
                finally:
                    closed = True

            return gen()

        monkeypatch.setattr(BambuClient, "camera_mjpeg", fake_camera_mjpeg)

    headers = {"X-API-Key": "secret"}
    with pytest.raises(RuntimeError):
        with client.stream("GET", "/api/p1/camera", headers=headers) as res:
            assert res.status_code == 200
            it = res.iter_bytes()
            assert next(it) == b"good"
            next(it)
    assert closed


def test_camera_stream_unsupported(client, monkeypatch):
    from state import BambuClient

    def fake_camera_mjpeg(self):
        return "not-bytes"

    monkeypatch.setattr(BambuClient, "camera_mjpeg", fake_camera_mjpeg)

    headers = {"X-API-Key": "secret"}
    res = client.get("/api/p1/camera", headers=headers)
    assert res.status_code in (501, 502)


def test_camera_stream_missing(client, monkeypatch):
    from state import BambuClient

    monkeypatch.delattr(BambuClient, "camera_mjpeg", raising=False)

    headers = {"X-API-Key": "secret"}
    res = client.get("/api/p1/camera", headers=headers)
    assert res.status_code == 501
