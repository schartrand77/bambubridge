"""
bambubridge v1.6 — FastAPI wrapper for Bambu LAN via pybambu 1.0.x

ENV VARS
--------
Required (name keys must match across all three):
  BAMBULAB_PRINTERS   = "babu@192.168.1.66;other@192.168.1.77"
  BAMBULAB_SERIALS    = "babu=SERIAL1;other=SERIAL2"
  BAMBULAB_LAN_KEYS   = "babu=ACCESSCODE1;other=ACCESSCODE2"

Optional:
  BAMBULAB_TYPES      = "babu=X1C;other=P1S"    # default X1C if missing
  BAMBULAB_REGION     = "US"                    # pybambu ctor expects this
  BAMBULAB_EMAIL      = ""                      # not needed for LAN-only
  BAMBULAB_USERNAME   = ""                      # not needed for LAN-only
  BAMBULAB_AUTH_TOKEN = ""                      # not needed for LAN-only
  BAMBULAB_AUTOCONNECT= "1"                     # "1/true/yes/on" = connect all on startup
  BAMBULAB_ALLOW_ORIGINS = ""                   # comma-separated CORS origins; default localhost only
  BAMBULAB_API_KEY    = ""                      # optional API key for protected endpoints

Notes:
- pybambu 1.0.x requires: device_type, serial, host, local_mqtt=True, access_code=...
- We default REGION/EMAIL/USERNAME/AUTH_TOKEN so you can run LAN-only.
"""

import os
import asyncio
import logging
import inspect
from typing import Dict, Any, Optional, Callable, AsyncGenerator, Generator

from pydantic import BaseModel, HttpUrl

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.security import APIKeyHeader

# ---- logging -----------------------------------------------------------------
log = logging.getLogger("bambubridge")

# ---- pybambu import ----------------------------------------------------------
try:
    from pybambu import BambuClient  # 1.0.x
except Exception as e:
    raise RuntimeError(f"Failed to import pybambu: {e}")

# ---- app ---------------------------------------------------------------------
app = FastAPI(
    title="Bambu LAN Bridge",
    version="1.6",
    docs_url=None,                 # we serve Swagger UI locally below
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

DEFAULT_ORIGINS = ["http://localhost", "http://127.0.0.1"]
ALLOW_ORIGINS = [o.strip() for o in os.getenv("BAMBULAB_ALLOW_ORIGINS", "").split(",") if o.strip()] or DEFAULT_ORIGINS

# CORS configuration (defaults to localhost only; override via BAMBULAB_ALLOW_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("BAMBULAB_API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def require_api_key(api_key: str = Security(api_key_header)) -> None:
    if API_KEY and api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")

# ---- Swagger UI assets served locally (no external CDN needed) ---------------
try:
    # pip install swagger-ui-bundle
    from swagger_ui_bundle import swagger_ui_path  # path to bundled dist
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
except Exception as _e:  # keep running even if package missing
    log.warning("swagger-ui-bundle not available; /docs will use CDN or be blank: %s", _e)

    @app.get("/docs", include_in_schema=False)
    def fallback_docs():
        # Falls back to FastAPI's default (may try to load from CDN)
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} — API",
        )

# ---- runtime state -----------------------------------------------------------


class PrinterState:
    """Holds printer connection state with concurrency guards."""

    def __init__(self) -> None:
        self.clients: Dict[str, BambuClient] = {}
        self.last_error: Dict[str, str] = {}
        self.lock = asyncio.Lock()

    async def get_client(self, name: str) -> Optional[BambuClient]:
        async with self.lock:
            return self.clients.get(name)

    async def set_client(self, name: str, client: BambuClient) -> None:
        async with self.lock:
            self.clients[name] = client
            self.last_error.pop(name, None)

    async def set_error(self, name: str, detail: str) -> None:
        async with self.lock:
            self.last_error[name] = detail

    async def snapshot(self) -> tuple[Dict[str, BambuClient], Dict[str, str]]:
        async with self.lock:
            return dict(self.clients), dict(self.last_error)

    async def clear(self) -> None:
        async with self.lock:
            self.clients.clear()
            self.last_error.clear()


state = PrinterState()

# ---- env helpers -------------------------------------------------------------
def _pairs(env: str) -> Dict[str, str]:
    """'name@host;other@host2' -> {name: host, ...}"""
    out: Dict[str, str] = {}
    raw = os.getenv(env, "")
    for part in filter(None, raw.split(";")):
        if "@" in part:
            n, h = part.split("@", 1)
            out[n.strip()] = h.strip()
    return out

def _kv(env: str) -> Dict[str, str]:
    """'name=value;other=value2' -> {name: value, ...}"""
    out: Dict[str, str] = {}
    raw = os.getenv(env, "")
    for part in filter(None, raw.split(";")):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out

PRINTERS   = _pairs("BAMBULAB_PRINTERS")    # name -> host
SERIALS    = _kv("BAMBULAB_SERIALS")        # name -> serial
LAN_KEYS   = _kv("BAMBULAB_LAN_KEYS")       # name -> access_code
TYPES      = _kv("BAMBULAB_TYPES")          # name -> model (X1C/P1S/A1...), default X1C
REGION     = os.getenv("BAMBULAB_REGION", "US")
EMAIL      = os.getenv("BAMBULAB_EMAIL", "")
USERNAME   = os.getenv("BAMBULAB_USERNAME", "")
AUTH_TOKEN = os.getenv("BAMBULAB_AUTH_TOKEN", "")
AUTOCONNECT= os.getenv("BAMBULAB_AUTOCONNECT", "0").lower() in {"1","true","yes","on"}


def _validate_env() -> None:
    """Cross-check name sets and ensure required fields exist."""
    names = set(PRINTERS) | set(SERIALS) | set(LAN_KEYS) | set(TYPES)
    missing_required: list[tuple[str, str]] = []
    for n in names:
        if n not in PRINTERS:
            missing_required.append((n, "BAMBULAB_PRINTERS"))
        if n not in SERIALS:
            missing_required.append((n, "BAMBULAB_SERIALS"))
        if n not in LAN_KEYS:
            missing_required.append((n, "BAMBULAB_LAN_KEYS"))
        if n not in TYPES:
            log.warning("Missing BAMBULAB_TYPES for '%s'; defaulting to X1C", n)
    if missing_required:
        for name, env in missing_required:
            log.error("Missing %s entry for '%s'", env, name)
        raise RuntimeError("Printer configuration incomplete; check environment variables")


_validate_env()

# ---- utility checks ----------------------------------------------------------
def _require_known(name: str):
    if name not in PRINTERS:
        raise HTTPException(404, f"Unknown printer '{name}'")
    if name not in SERIALS:
        raise HTTPException(400, f"Missing serial for '{name}' (set BAMBULAB_SERIALS)")
    if name not in LAN_KEYS:
        raise HTTPException(400, f"Missing access code for '{name}' (set BAMBULAB_LAN_KEYS)")

def _pick(obj: Any, names: tuple[str, ...]) -> Optional[Callable]:
    for n in names:
        fn = getattr(obj, n, None)
        if callable(fn):
            return fn
    return None

# ---- connection core ---------------------------------------------------------
async def _connect(name: str, raise_http: bool = True) -> BambuClient:
    """Ensure a connected BambuClient; return it or raise HTTP error."""
    _require_known(name)

    c = await state.get_client(name)
    if c and getattr(c, "connected", False):
        return c

    host   = PRINTERS[name]
    serial = SERIALS[name]
    access = LAN_KEYS[name]
    dtype  = TYPES.get(name, "X1C")

    try:
        c = BambuClient(
            device_type=dtype,
            serial=serial,
            host=host,
            local_mqtt=True,
            access_code=access,      # correct kwarg for pybambu 1.0.x
            region=REGION,
            email=EMAIL,
            username=USERNAME,
            auth_token=AUTH_TOKEN,
        )
        # Start LAN MQTT (spawns internal threads)
        c.connect(callback=lambda evt: None)

        # Wait briefly (~5s) for connected flag
        for _ in range(50):
            if c.connected:
                break
            await asyncio.sleep(0.1)

        if not c.connected:
            raise RuntimeError("Printer MQTT connected=False after wait")

        await state.set_client(name, c)
        log.info("connected: %s@%s (%s)", name, host, serial)
        return c

    except Exception as e:
        detail = f"{type(e).__name__}: {e}"
        await state.set_error(name, detail)
        log.warning("connect(%s) failed: %s", name, detail)
        if raise_http:
            raise HTTPException(status_code=502, detail=f"connect failed: {detail}")
        raise

# ---- optional autoconnect on startup -----------------------------------------
@app.on_event("startup")
async def _startup():
    if not AUTOCONNECT:
        log.info("startup: lazy mode (BAMBULAB_AUTOCONNECT not set)")
        return
    log.info("startup: autoconnect enabled")
    async def warm(n: str):
        try:
            await _connect(n, raise_http=False)
        except Exception as e:
            log.warning("warm(%s) error: %s", n, e)
    await asyncio.gather(*[warm(n) for n in PRINTERS])


# ---- graceful shutdown -------------------------------------------------------
@app.on_event("shutdown")
async def _shutdown() -> None:
    """Disconnect all active printer clients and reset state."""
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
        except Exception as e:
            log.warning("shutdown: disconnect(%s) failed: %s", name, e)

    await asyncio.gather(*(_disc(n, c) for n, c in clients_snapshot.items()))
    await state.clear()


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
        out.append({
            "name": n,
            "host": host,
            "serial": SERIALS.get(n),
            "connected": bool(c and getattr(c, "connected", False)),
            "last_error": errors_snapshot.get(n),
        })
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
    except Exception as e:
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
    # Optional blobs if present in your pybambu build
    try:
        if getattr(dev, "get_version_data", None):
            data["get_version"] = dev.get_version_data
        if getattr(dev, "push_all_data", None):
            data["push_all"] = dev.push_all_data
    except Exception as e:
        data["note"] = f"status extras unavailable: {type(e).__name__}"
    return JSONResponse(data)

@app.post("/api/{name}/print", dependencies=[Depends(require_api_key)])
async def start_print(name: str, job: JobRequest):
    """
    Body: {"gcode_url": "http://...", "thmf_url": "http://..."}  # thmf_url optional
    """
    c = await _connect(name)
    fn = _pick(c, ("start_print_from_url", "start_print"))
    if not fn:
        raise HTTPException(501, "pybambu missing print-from-url API")
    try:
        try:
            kwargs = {"gcode_url": str(job.gcode_url)}
            if job.thmf_url:
                kwargs["thmf_url"] = str(job.thmf_url)
            return fn(**kwargs)  # preferred
        except TypeError:
            kwargs = {"url": str(job.gcode_url)}
            if job.thmf_url:
                kwargs["thmf_url"] = str(job.thmf_url)
            try:
                return fn(**kwargs)
            except TypeError:
                if job.thmf_url:
                    return fn(str(job.gcode_url), str(job.thmf_url))
                return fn(str(job.gcode_url))
    except Exception as e:
        raise HTTPException(502, detail=f"start_print failed: {type(e).__name__}: {e}")

@app.post("/api/{name}/pause", dependencies=[Depends(require_api_key)])
async def pause(name: str):
    c = await _connect(name)
    fn = _pick(c, ("pause_print", "pause"))
    if not fn:
        raise HTTPException(501, "pybambu missing pause API")
    try:
        return fn()
    except Exception as e:
        raise HTTPException(502, detail=f"pause failed: {type(e).__name__}: {e}")

@app.post("/api/{name}/resume", dependencies=[Depends(require_api_key)])
async def resume(name: str):
    c = await _connect(name)
    fn = _pick(c, ("resume_print", "resume"))
    if not fn:
        raise HTTPException(501, "pybambu missing resume API")
    try:
        return fn()
    except Exception as e:
        raise HTTPException(502, detail=f"resume failed: {type(e).__name__}: {e}")

@app.post("/api/{name}/stop", dependencies=[Depends(require_api_key)])
async def stop(name: str):
    c = await _connect(name)
    fn = _pick(c, ("stop_print", "stop"))
    if not fn:
        raise HTTPException(501, "pybambu missing stop API")
    try:
        return fn()
    except Exception as e:
        raise HTTPException(502, detail=f"stop failed: {type(e).__name__}: {e}")

@app.get("/api/{name}/camera", dependencies=[Depends(require_api_key)])
async def camera(name: str):
    """
    MJPEG passthrough if your pybambu build exposes it; otherwise 501.
    We support both async and sync generators.
    """
    c = await _connect(name)
    gen = getattr(c, "camera_mjpeg", None)
    if not callable(gen):
        raise HTTPException(501, "Camera MJPEG not available in this pybambu build")

    try:
        candidate = gen  # function or generator
        # If it's a function, call it to see what we get.
        if inspect.isfunction(gen) or inspect.ismethod(gen):
            candidate = gen()

        # Async generator?
        if inspect.isasyncgen(candidate):
            async def astream() -> AsyncGenerator[bytes, None]:
                async for chunk in candidate:
                    yield chunk
            return StreamingResponse(astream(), media_type="multipart/x-mixed-replace; boundary=frame")

        # Sync generator?
        if inspect.isgenerator(candidate):
            def sstream() -> Generator[bytes, None, None]:
                for chunk in candidate:
                    yield chunk
            return StreamingResponse(sstream(), media_type="multipart/x-mixed-replace; boundary=frame")

        # Unknown type
        raise HTTPException(501, "camera_mjpeg returned unsupported type")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, detail=f"camera stream error: {type(e).__name__}: {e}")


def main() -> None:
    """Run the FastAPI application with a basic logging configuration."""
    level_name = os.getenv("BAMBULAB_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(levelname)s:%(name)s:%(message)s",
    )
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8088")))


if __name__ == "__main__":
    main()
