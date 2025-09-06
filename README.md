# bambubridge

FastAPI wrapper for Bambu Lab printers exposed over the local network via [pybambu](https://pypi.org/project/pybambu/).

## Unraid Docker

An Unraid Docker template is provided in [`bambubridge.xml`](bambubridge.xml). To install:

1. Copy the file to `/boot/config/plugins/dockerMan/templates-user/` on your Unraid server or use the **Add Container** button in the Docker tab and select *Template* > *Upload* to import it.
2. The template exposes port `8288` (mapped to `8088` in the container) and defines environment variables for printer configuration:
   - `BAMBULAB_PRINTERS`
   - `BAMBULAB_SERIALS`
   - `BAMBULAB_LAN_KEYS`
   - optional: `BAMBULAB_TYPES`, `BAMBULAB_REGION`, `BAMBULAB_AUTOCONNECT`
3. After the container starts, open `http://<server-ip>:8288/docs` for the web UI and API documentation.

A standard [`Dockerfile`](Dockerfile) is also included if you wish to build the image yourself.
