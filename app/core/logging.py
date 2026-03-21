import logging
import sys

from pythonjsonlogger import json as json_logger


def setup_logging(env: str, log_level: str = "INFO") -> None:
    level_map = {
        "local": "DEBUG",
        "staging": "INFO",
        "production": "WARNING",
    }
    level = level_map.get(env, log_level)

    formatter = json_logger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn loggers
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.addHandler(handler)
        uv_logger.setLevel(level)

    # Suppress noisy loggers
    logging.getLogger("ppocr").setLevel(logging.ERROR)
    logging.getLogger("paddle").setLevel(logging.ERROR)
