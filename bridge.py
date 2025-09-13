"""Application entrypoint for bambubridge."""

from __future__ import annotations

import logging
import os

import uvicorn

from api import app


def main() -> None:
    level_name = os.getenv("BAMBULAB_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    invalid_level = not isinstance(level, int)
    if invalid_level:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    if invalid_level:
        logging.warning(
            "Invalid log level %s provided, falling back to INFO", level_name
        )
    port_env = os.getenv("PORT", "8088")
    try:
        port = int(port_env)
    except ValueError:
        port = 8088
        logging.warning(
            "Invalid port %s provided, falling back to 8088",
            port_env,
        )
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
