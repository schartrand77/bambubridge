"""FastAPI application for Bambu LAN bridge."""

from __future__ import annotations

import asyncio
import logging
import inspect
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, Callable, AsyncGenerator, Generator

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, HttpUrl

from config import (
    PRINTERS,
    SERIALS,
    ALLOW_ORIGINS,
    API_KEY,
    AUTOCONNECT,
)
from state import state, _connect, _require_known, BambuClient

log = logging.getLogger("bambubridge")


# ---- lifespan -----------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if not AUTOCONNECT:
        log.info("startup: lazy mode (BAMBULAB_AUTOCONNECT not set)")
    else:
        log.info("startup: autoconnect enabled")

        async def warm(n: str) -> None:
            try:
                await _connect(n, raise_http=False)
            except Exception as e:  # pragma: no cover - connection errors
                log.warning("warm(%s) error: %s", n, e)

        await asyncio.gather(*[warm(n) for n in PRINTERS])
    try:
        yield
    finally:
        clients_snapshot, _ = await state.snapshot()

        async def _disc(name: str, client: BambuClient) -> None:
            fn = _pick(client, ("disconnect", "close"))
            if not fn:
                return
            try:
                if inspect.iscoroutinefunction(fn):
                    await fn()
                else:
                    await asyncio.to_thread(fn)
                log.info("shutdown: disconnected %s", name)
            except Exception as e:  # pragma: no cover - disconnect issues
                log.warning("shutdown: disconnect(%s) failed: %s", name, e)

        await asyncio.gather(*(_disc(n, c) for n, c in clients_snapshot.items()))
        await state.clear()


# ---- app ----------------------------------------------------------------------
app = FastAPI(
    title="Bambu LAN Bridge",
    version="1.6",
    docs_url=None,
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS configuration (defaults to localhost only; override via BAMBULAB_ALLOW_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(api_key_header)) -> None:
    if API_KEY and api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


# ---- Swagger UI assets served locally (no external CDN needed) ---------------
try:
    from swagger_ui_bundle import swagger_ui_path  # type: ignore

    app.mount("/_docs", StaticFiles(directory=swagger_ui_path), name="swagger_static")

    @app.get("/docs", include_in_schema=False)
    def _docs():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} — API",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="/_docs/swagger-ui-bundle.js",
            swagger_css_url="/_docs/swagger-ui.css",
        )

    @app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
    def swagger_ui_redirect():
        return get_swagger_ui_oauth2_redirect_html()
except Exception as _e:  # pragma: no cover - optional dependency missing
    log.warning("swagger-ui-bundle not available; /docs may be blank: %s", _e)

    @app.get("/docs", include_in_schema=False)
    def fallback_docs():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} — API",
        )


# ---- helpers -----------------------------------------------------------------

def _pick(obj: Any, names: tuple[str, ...]) -> Optional[Callable]:
    for n in names:
        fn = getattr(obj, n, None)
        if callable(fn):
            return fn
    return None


# ---- request models -----------------------------------------------------------


class JobRequest(BaseModel):
    """Request body for starting a print job."""

    gcode_url: HttpUrl
    thmf_url: Optional[HttpUrl] = None


# ---- routes ------------------------------------------------------------------


@app.get("/healthz")
async def healthz():
    return {"ok": True, "printers": list(PRINTERS.keys())}


@app.get("/api/printers")
async def list_printers():
    out = []
    clients_snapshot, errors_snapshot = await state.snapshot()
    for n, host in PRINTERS.items():
        c = clients_snapshot.get(n)
        out.append(
            {
                "name": n,
                "host": host,
                "serial": SERIALS.get(n),
                "connected": bool(c and getattr(c, "connected", False)),
                "last_error": errors_snapshot.get(n),
            }
        )
    return out


@app.post("/api/{name}/connect", dependencies=[Depends(require_api_key)])
async def connect_now(name: str):
    c = await _connect(name)
    return {"ok": True, "name": name, "host": c.host, "serial": SERIALS.get(name)}


@app.post("/api/{name}/disconnect", dependencies=[Depends(require_api_key)])
async def disconnect_now(name: str):
    _require_known(name)
    c = await state.get_client(name)
    if not c:
        raise HTTPException(404, "Not connected")
    fn = _pick(c, ("disconnect", "close"))
    if not fn:
        raise HTTPException(501, "pybambu missing disconnect API")
    try:
        if inspect.iscoroutinefunction(fn):
            await fn()
        else:
            await asyncio.to_thread(fn)
    except Exception as e:  # pragma: no cover - network failures
        raise HTTPException(502, detail=f"disconnect failed: {type(e).__name__}: {e}")
    async with state.lock:
        state.clients.pop(name, None)
    return {"ok": True, "name": name}


@app.get("/api/{name}/status")
async def status(name: str):
    c = await _connect(name)
    dev = c.get_device()
    data: Dict[str, Any] = {
        "name": name,
        "host": c.host,
        "serial": SERIALS.get(name),
        "connected": c.connected,
    }
    try:
        if getattr(dev, "get_version_data", None):
            data["get_version"] = dev.get_version_data
        if getattr(dev, "push_all_data", None):
            data["push_all"] = dev.push_all_data
    except Exception as e:  # pragma: no cover - pybambu variations
        data["note"] = f"status extras unavailable: {type(e).__name__}"
    return JSONResponse(data)


@app.post("/api/{name}/print", dependencies=[Depends(require_api_key)])
async def start_print(name: str, job: JobRequest):
    c = await _connect(name)
    fn = _pick(c, ("start_print_from_url", "start_print")) or _pick(
        c.get_device(), ("start_print_from_url", "start_print")
    )
    if not fn:
        raise HTTPException(501, "pybambu missing print-from-url API")
    try:
        try:
            kwargs = {"gcode_url": str(job.gcode_url)}
            if job.thmf_url:
                kwargs["thmf_url"] = str(job.thmf_url)
            if inspect.iscoroutinefunction(fn):
                return await fn(**kwargs)
            return await asyncio.to_thread(fn, **kwargs)
        except TypeError:
            kwargs = {"url": str(job.gcode_url)}
            if job.thmf_url:
                kwargs["thmf_url"] = str(job.thmf_url)
            try:
                if inspect.iscoroutinefunction(fn):
                    return await fn(**kwargs)
                return await asyncio.to_thread(fn, **kwargs)
            except TypeError:
                if job.thmf_url:
                    args = (str(job.gcode_url), str(job.thmf_url))
                else:
                    args = (str(job.gcode_url),)
                if inspect.iscoroutinefunction(fn):
                    return await fn(*args)
                return await asyncio.to_thread(fn, *args)
    except Exception as e:  # pragma: no cover - pybambu variations
        raise HTTPException(502, detail=f"start_print failed: {type(e).__name__}: {e}")


@app.post("/api/{name}/pause", dependencies=[Depends(require_api_key)])
async def pause(name: str):
    c = await _connect(name)
    fn = _pick(c, ("pause_print", "pause")) or _pick(
        c.get_device(), ("pause_print", "pause")
    )
    if not fn:
        raise HTTPException(501, "pybambu missing pause API")
    try:
        if inspect.iscoroutinefunction(fn):
            return await fn()
        return await asyncio.to_thread(fn)
    except Exception as e:  # pragma: no cover
        raise HTTPException(502, detail=f"pause failed: {type(e).__name__}: {e}")


@app.post("/api/{name}/resume", dependencies=[Depends(require_api_key)])
async def resume(name: str):
    c = await _connect(name)
    fn = _pick(c, ("resume_print", "resume")) or _pick(
        c.get_device(), ("resume_print", "resume")
    )
    if not fn:
        raise HTTPException(501, "pybambu missing resume API")
    try:
        if inspect.iscoroutinefunction(fn):
            return await fn()
        return await asyncio.to_thread(fn)
    except Exception as e:  # pragma: no cover
        raise HTTPException(502, detail=f"resume failed: {type(e).__name__}: {e}")


@app.post("/api/{name}/stop", dependencies=[Depends(require_api_key)])
async def stop(name: str):
    c = await _connect(name)
    fn = _pick(c, ("stop_print", "stop")) or _pick(
        c.get_device(), ("stop_print", "stop")
    )
    if not fn:
        raise HTTPException(501, "pybambu missing stop API")
    try:
        if inspect.iscoroutinefunction(fn):
            return await fn()
        return await asyncio.to_thread(fn)
    except Exception as e:  # pragma: no cover
        raise HTTPException(502, detail=f"stop failed: {type(e).__name__}: {e}")


@app.get("/api/{name}/camera", dependencies=[Depends(require_api_key)])
async def camera(name: str):
    c = await _connect(name)
    gen = getattr(c, "camera_mjpeg", None)
    if not callable(gen):
        raise HTTPException(501, "Camera MJPEG not available in this pybambu build")

    try:
        candidate = gen
        if inspect.isfunction(gen) or inspect.ismethod(gen):
            candidate = gen()

        if inspect.isasyncgen(candidate):
            async def astream() -> AsyncGenerator[bytes, None]:
                async for chunk in candidate:
                    yield chunk
            return StreamingResponse(
                astream(),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )

        if inspect.isgenerator(candidate):
            def sstream() -> Generator[bytes, None, None]:
                for chunk in candidate:
                    yield chunk
            return StreamingResponse(
                sstream(),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )

        raise HTTPException(501, "camera_mjpeg returned unsupported type")
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        raise HTTPException(502, detail=f"camera stream error: {type(e).__name__}: {e}")
