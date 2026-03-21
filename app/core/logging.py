import logging
import sys

from pythonjsonlogger import json as json_logger


def setup_logging(env: str, log_level: str = "INFO", es_url: str | None = None,
                  es_index: str = "signlab-business-logs", es_enabled: bool = False) -> None:
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

    # Elasticsearch handler for business logs (signlab.* namespace)
    if es_enabled and es_url:
        from app.core.es_handler import ElasticsearchHandler
        es_handler = ElasticsearchHandler(es_url=es_url, index=es_index)
        es_handler.setFormatter(formatter)

        # Attach to the signlab business logger namespace only
        # Always use INFO for business logs — production root level (WARNING)
        # must not filter out INFO-level OCR/liveness logs bound for Elasticsearch.
        biz_logger = logging.getLogger("signlab")
        biz_logger.addHandler(es_handler)
        biz_logger.setLevel(logging.INFO)

        logging.getLogger(__name__).info(
            "Elasticsearch business log handler enabled",
            extra={"es_url": es_url, "es_index": es_index},
        )
