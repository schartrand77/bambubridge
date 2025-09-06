# bambubridge

FastAPI wrapper for Bambu Lab printers exposed over the local network via [pybambu](https://pypi.org/project/pybambu/).

## Unraid Docker

An Unraid Docker template is provided in [`bambubridge.xml`](bambubridge.xml). To install:

1. Copy the file to `/boot/config/plugins/dockerMan/templates-user/` on your Unraid server or use the **Add Container** button in the Docker tab and select *Template* > *Upload* to import it.
2. The template exposes port `8288` (mapped to `8088` in the container) and defines environment variables for printer configuration:
   - `BAMBULAB_PRINTERS`
   - `BAMBULAB_SERIALS`
   - `BAMBULAB_LAN_KEYS`
   - optional: `BAMBULAB_TYPES`, `BAMBULAB_REGION`, `BAMBULAB_AUTOCONNECT`, `BAMBULAB_ALLOW_ORIGINS`, `BAMBULAB_API_KEY`, `BAMBULAB_LOG_LEVEL`
     - `BAMBULAB_ALLOW_ORIGINS` defaults to only `http://localhost` and `http://127.0.0.1`
     - set `BAMBULAB_API_KEY` to require the same value in the `X-API-Key` header on write endpoints
     - `BAMBULAB_LOG_LEVEL` controls logging verbosity (default `INFO`)
3. After the container starts, open `http://<server-ip>:8288/docs` for the web UI and API documentation.

A standard [`Dockerfile`](Dockerfile) is also included if you wish to build the image yourself.

## API

To start a print job, POST to `/api/{name}/print` with a JSON body matching the
`JobRequest` model:

```bash
curl -X POST http://<server-ip>:8288/api/<printer>/print \
  -H 'Content-Type: application/json' \
  -d '{"gcode_url": "http://example.com/file.gcode", "thmf_url": "http://example.com/file.thmf"}'
```

`gcode_url` is required; `thmf_url` may be omitted.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
