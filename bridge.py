"""Application entrypoint for bambubridge."""

from __future__ import annotations

import logging
import os

import uvicorn

from api import app
import config


def main() -> None:
    level_name = os.getenv("BAMBULAB_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(levelname)s:%(name)s:%(message)s",
    )
    config._validate_env()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8088")))


if __name__ == "__main__":
    main()
