"""FastAPI application for Bambu LAN bridge."""

from __future__ import annotations

import asyncio
import logging
import inspect
import secrets
from contextlib import asynccontextmanager, closing, aclosing
from typing import Dict, Any, Optional, Callable, AsyncGenerator, Generator

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, HttpUrl, Field

try:  # pragma: no cover - import resolution differs for packaging
    from . import __version__
except Exception:  # pragma: no cover - fallback for direct execution
    from __init__ import __version__

import config
from config import (
    PRINTERS,
    SERIALS,
    AUTOCONNECT,
)
from state import state, _connect, _require_known, BambuClient
from utils import _pick

log = logging.getLogger("bambubridge")


# ---- lifespan -----------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    config._validate_env()
    with config.read_lock():
        api_key = config.API_KEY
        printer_names = list(PRINTERS)
    if not api_key:
        raise RuntimeError("API key not configured")
    if not AUTOCONNECT:
        log.info("startup: lazy mode (BAMBULAB_AUTOCONNECT not set)")
    else:
        log.info("startup: autoconnect enabled")

        async def warm(n: str) -> None:
            try:
                await _connect(n, raise_http=False)
            except Exception as e:  # pragma: no cover - connection errors
                log.warning("warm(%s) error: %s", n, e)

        await asyncio.gather(*[warm(n) for n in printer_names])
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
    version=__version__,
    docs_url=None,
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS configuration (defaults to localhost only; override via BAMBULAB_ALLOW_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(api_key_header)) -> None:
    with config.read_lock():
        expected_api_key = config.API_KEY
    if expected_api_key is None:
        raise HTTPException(
            status_code=500,
            detail="API key not configured",
        )
    if not api_key or not secrets.compare_digest(api_key, expected_api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API-Key"},
        )


# ---- Swagger UI assets served locally (no external CDN needed) ---------------
try:
    from swagger_ui_bundle import swagger_ui_path  # type: ignore

    app.mount("/_docs", StaticFiles(directory=swagger_ui_path), name="swagger_static")

    @app.get("/docs", include_in_schema=False)
    def _docs():
        """Serve Swagger UI HTML for the API."""
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} — API",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="/_docs/swagger-ui-bundle.js",
            swagger_css_url="/_docs/swagger-ui.css",
        )

    @app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
    def swagger_ui_redirect():
        """Serve OAuth2 redirect HTML used by Swagger UI."""
        return get_swagger_ui_oauth2_redirect_html()
except Exception as _e:  # pragma: no cover - optional dependency missing
    log.warning("swagger-ui-bundle not available; /docs may be blank: %s", _e)

    @app.get("/docs", include_in_schema=False)
    def fallback_docs():
        """Serve basic Swagger UI HTML when bundle is unavailable."""
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} — API",
        )


# ---- helpers -----------------------------------------------------------------


async def _run_printer_action(
    name: str, action: str, methods: tuple[str, ...]
) -> ActionResult:
    """Locate and invoke an action on a printer client or its device."""

    c = await _connect(name)
    fn = _pick(c, methods) or _pick(c.get_device(), methods)
    if not fn:
        raise HTTPException(501, f"pybambu missing {action} API")
    try:
        if inspect.iscoroutinefunction(fn):
            res = await fn()
        else:
            res = await asyncio.to_thread(fn)
    except Exception as e:  # pragma: no cover - network failures
        raise HTTPException(502, detail=f"{action} failed: {type(e).__name__}: {e}")
    data = res if isinstance(res, dict) else {"response": res}
    return ActionResult(result=data)


async def _invoke_print(
    fn: Callable[..., Any], gcode_url: str, thmf_url: Optional[str]
) -> Any:
    """Invoke a print function with normalized signatures.

    ``pybambu`` has exposed a few different call signatures for starting a
    print.  Rather than attempting multiple calls, inspect ``fn`` to determine
    how to pass the ``gcode_url`` and optional ``thmf_url`` parameters.
    """

    sig = inspect.signature(fn)
    param_names = [p.name for p in sig.parameters.values()]

    args: list[Any] = []
    kwargs: dict[str, Any] = {}

    if "gcode_url" in param_names:
        kwargs["gcode_url"] = gcode_url
    elif "url" in param_names:
        kwargs["url"] = gcode_url
    else:
        args.append(gcode_url)

    if thmf_url is not None:
        if "thmf_url" in param_names:
            kwargs["thmf_url"] = thmf_url
        else:
            args.append(thmf_url)

    is_coro = inspect.iscoroutinefunction(fn)
    try:
        if is_coro:
            return await fn(*args, **kwargs)
        return await asyncio.to_thread(fn, *args, **kwargs)
    except TypeError as e:
        tb = e.__traceback__
        fn_code = getattr(fn, "__code__", None)
        while tb:
            if tb.tb_frame.f_code is fn_code:
                # Exception originated inside ``fn``; propagate.
                raise
            tb = tb.tb_next
        raise TypeError(
            "Unsupported function signature. Expected to accept 'gcode_url' or 'url' and optional 'thmf_url'."
        ) from None



# ---- request models -----------------------------------------------------------


class JobRequest(BaseModel):
    """Request body for starting a print job."""

    gcode_url: HttpUrl
    thmf_url: Optional[HttpUrl] = None


class PrinterInfo(BaseModel):
    """Details about a configured printer."""

    name: str
    host: str
    serial: Optional[str] = None
    connected: bool
    last_error: Optional[str] = None


class StatusResult(BaseModel):
    """Standard response wrapper for status information."""

    ok: bool = True
    status: Dict[str, Any] = Field(default_factory=dict)


class ActionResult(BaseModel):
    """Standard response wrapper for printer actions."""

    ok: bool = True
    result: Dict[str, Any] = Field(default_factory=dict)


# ---- routes ------------------------------------------------------------------


@app.get("/healthz")
async def healthz() -> StatusResult:
    """Return API health status and list of known printers."""
    with config.read_lock():
        names = list(PRINTERS.keys())
    return StatusResult(status={"printers": names})


@app.get("/api/printers")
async def list_printers() -> list[PrinterInfo]:
    """List configured printers and their connection status."""
    out: list[PrinterInfo] = []
    with config.read_lock():
        printer_items = list(PRINTERS.items())
        serials = dict(SERIALS)
    clients_snapshot, errors_snapshot = await state.snapshot()
    for n, host in printer_items:
        c = clients_snapshot.get(n)
        out.append(
            PrinterInfo(
                name=n,
                host=host,
                serial=serials.get(n),
                connected=bool(c and getattr(c, "connected", False)),
                last_error=errors_snapshot.get(n),
            )
        )
    return out


@app.post("/api/{name}/connect", dependencies=[Depends(require_api_key)])
async def connect_now(name: str) -> StatusResult:
    """Connect to a printer and return its details."""
    c = await _connect(name)
    with config.read_lock():
        serial = SERIALS.get(name)
    return StatusResult(status={"name": name, "host": c.host, "serial": serial})


@app.post("/api/{name}/disconnect", dependencies=[Depends(require_api_key)])
async def disconnect_now(name: str) -> ActionResult:
    """Disconnect from a printer and confirm the action."""
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
    async with state.write_lock:
        state.clients.pop(name, None)
    return ActionResult(result={"name": name})


@app.get("/api/{name}/status")
async def status(name: str) -> StatusResult:
    """Return status information for a printer as JSON."""
    c = await _connect(name)
    dev = c.get_device()
    with config.read_lock():
        serial = SERIALS.get(name)
    data: Dict[str, Any] = {
        "name": name,
        "host": c.host,
        "serial": serial,
        "connected": c.connected,
    }
    try:
        if getattr(dev, "get_version_data", None):
            data["get_version"] = dev.get_version_data
        if getattr(dev, "push_all_data", None):
            data["push_all"] = dev.push_all_data
    except Exception as e:  # pragma: no cover - pybambu variations
        data["note"] = f"status extras unavailable: {type(e).__name__}"
    return StatusResult(status=data)


@app.post("/api/{name}/print", dependencies=[Depends(require_api_key)])
async def start_print(name: str, job: JobRequest) -> ActionResult:
    """Start a print job and return the printer's response."""
    c = await _connect(name)
    fn = _pick(c, ("start_print_from_url", "start_print")) or _pick(
        c.get_device(), ("start_print_from_url", "start_print")
    )
    if not fn:
        raise HTTPException(501, "pybambu missing print-from-url API")
    try:
        res = await _invoke_print(
            fn,
            str(job.gcode_url),
            str(job.thmf_url) if job.thmf_url else None,
        )
    except Exception as e:  # pragma: no cover - pybambu variations
        raise HTTPException(502, detail=f"start_print failed: {type(e).__name__}: {e}")
    data = res if isinstance(res, dict) else {"response": res}
    return ActionResult(result=data)


@app.post("/api/{name}/pause", dependencies=[Depends(require_api_key)])
async def pause(name: str) -> ActionResult:
    """Pause the active print job and return the result."""
    return await _run_printer_action(name, "pause", ("pause_print", "pause"))


@app.post("/api/{name}/resume", dependencies=[Depends(require_api_key)])
async def resume(name: str) -> ActionResult:
    """Resume a paused print job and return the result."""
    return await _run_printer_action(name, "resume", ("resume_print", "resume"))


@app.post("/api/{name}/stop", dependencies=[Depends(require_api_key)])
async def stop(name: str) -> ActionResult:
    """Stop the current print job and return the result."""
    return await _run_printer_action(name, "stop", ("stop_print", "stop"))


@app.get("/api/{name}/camera", dependencies=[Depends(require_api_key)])
async def camera(name: str):
    """Stream the printer camera as an MJPEG ``StreamingResponse``.

    Supports both synchronous and asynchronous ``camera_mjpeg`` implementations
    provided by :mod:`pybambu`.
    """

    c = await _connect(name)
    gen = getattr(c, "camera_mjpeg", None)
    if gen is None:
        raise HTTPException(501, "Camera MJPEG not available in this pybambu build")

    try:
        candidate = gen() if callable(gen) else gen
        if inspect.isawaitable(candidate):
            candidate = await candidate

        if inspect.isasyncgen(candidate):
            async def astream() -> AsyncGenerator[bytes, None]:
                async with aclosing(candidate) as agen:
                    async for chunk in agen:
                        if not isinstance(chunk, (bytes, bytearray)):
                            await agen.aclose()
                            raise HTTPException(
                                502, "camera stream yielded non-bytes chunk"
                            )
                        yield chunk

            return StreamingResponse(
                astream(),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )

        if inspect.isgenerator(candidate):
            def sstream() -> Generator[bytes, None, None]:
                with closing(candidate) as gen:
                    for chunk in gen:
                        if not isinstance(chunk, (bytes, bytearray)):
                            gen.close()
                            raise HTTPException(
                                502, "camera stream yielded non-bytes chunk"
                            )
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
