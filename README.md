# bambubridge

FastAPI wrapper for Bambu Lab printers exposed over the local network via [pybambu](https://pypi.org/project/pybambu/).

**Configuration requires setting an API key via the `BAMBULAB_API_KEY` environment variable.**

## Unraid Docker

An Unraid Docker template is provided in [`bambubridge.xml`](bambubridge.xml). To install:

1. Copy the file to `/boot/config/plugins/dockerMan/templates-user/` on your Unraid server or use the **Add Container** button in the Docker tab and select *Template* > *Upload* to import it.
2. The template exposes port `8288` (mapped to `8088` in the container) and defines environment variables for printer configuration:
   - `BAMBULAB_PRINTERS`
   - `BAMBULAB_SERIALS`
   - `BAMBULAB_LAN_KEYS`
   - `BAMBULAB_API_KEY` (value clients must supply in the `X-API-Key` header)
   - optional: `BAMBULAB_TYPES`, `BAMBULAB_REGION`, `BAMBULAB_AUTOCONNECT`, `BAMBULAB_ALLOW_ORIGINS`, `BAMBULAB_LOG_LEVEL`, `BAMBULAB_CONNECT_INTERVAL`, `BAMBULAB_CONNECT_TIMEOUT`, `BAMBULAB_EMAIL`, `BAMBULAB_USERNAME`, `BAMBULAB_AUTH_TOKEN`
     - `BAMBULAB_ALLOW_ORIGINS` defaults to only `http://localhost` and `http://127.0.0.1`
     - `BAMBULAB_LOG_LEVEL` controls logging verbosity (default `INFO`)
     - `BAMBULAB_CONNECT_INTERVAL` seconds between post-connect status checks (default `0.1`)
     - `BAMBULAB_CONNECT_TIMEOUT` total seconds to wait for connection (default `5`)
     - `BAMBULAB_EMAIL` email address for a Bambu Lab account
     - `BAMBULAB_USERNAME` username for the Bambu Lab account
     - `BAMBULAB_AUTH_TOKEN` authentication token associated with the account
3. After the container starts, open `http://<server-ip>:8288/docs` for the web UI and API documentation.

A standard [`Dockerfile`](Dockerfile) is also included if you wish to build the image yourself.

## API

All write endpoints require an `X-API-Key` header matching the `BAMBULAB_API_KEY` value.

To start a print job, POST to `/api/{name}/print` with a JSON body matching the
`JobRequest` model:

```bash
curl -X POST http://<server-ip>:8288/api/<printer>/print \
  -H 'Content-Type: application/json' \
  -d '{"gcode_url": "http://example.com/file.gcode", "thmf_url": "http://example.com/file.thmf"}'
```

`gcode_url` is required; `thmf_url` may be omitted.

### Camera streaming

To stream live MJPEG from a printer, send a `GET` request to
`/api/{name}/camera`.  The underlying `pybambu` client may expose
`camera_mjpeg` as either a synchronous or asynchronous function returning a
generator.  `bambubridge` detects both forms and will await an async
implementation automatically.

## Development

Install the development dependencies to run the test suite:

```bash
pip install -r requirements-dev.txt
pytest
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
