"""Application entrypoint for bambubridge."""

from __future__ import annotations

import logging
import os

import uvicorn

from api import app


def main() -> None:
    level_name = os.getenv("BAMBULAB_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s:%(name)s:%(message)s",
        )
        logging.warning(
            "Invalid log level %s provided, falling back to INFO", level_name
        )
    else:
        logging.basicConfig(
            level=level,
            format="%(levelname)s:%(name)s:%(message)s",
        )
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8088")))


if __name__ == "__main__":
    main()
