"""
Elasticsearch logging handler for business logs.

Sends structured JSON log records to Elasticsearch asynchronously
using a background queue to avoid blocking the request thread.
"""

import logging
import threading
import queue
from datetime import datetime, timezone


class ElasticsearchHandler(logging.Handler):
    """Buffers log records and ships them to Elasticsearch in a background thread."""

    def __init__(self, es_url: str, index: str, flush_interval: float = 5.0, max_batch: int = 50):
        super().__init__()
        self._es_url = es_url
        self._index = index
        self._flush_interval = flush_interval
        self._max_batch = max_batch
        self._queue: queue.Queue = queue.Queue(maxsize=10_000)
        self._client = None
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _get_client(self):
        if self._client is None:
            from elasticsearch import Elasticsearch
            self._client = Elasticsearch(
                self._es_url,
                verify_certs=False,
                request_timeout=10,
            )
            # Auto-create index if missing
            if not self._client.indices.exists(index=self._index):
                self._client.indices.create(
                    index=self._index,
                    mappings={
                        "properties": {
                            "timestamp": {"type": "date"},
                            "level": {"type": "keyword"},
                            "logger": {"type": "keyword"},
                            "message": {"type": "text"},
                            "step": {"type": "keyword"},
                            "document_type": {"type": "keyword"},
                            "side": {"type": "keyword"},
                            "request_id": {"type": "keyword"},
                            "user_id": {"type": "integer"},
                            "tx_id": {"type": "keyword"},
                            "client_ip": {"type": "ip"},
                            "duration_ms": {"type": "float"},
                            "ocr_text_count": {"type": "integer"},
                            "extracted_fields": {"type": "keyword"},
                            "error": {"type": "text"},
                            "result": {"type": "keyword"},
                            "score": {"type": "float"},
                            "liveness_score": {"type": "float"},
                        }
                    },
                )
        return self._client

    def emit(self, record: logging.LogRecord):
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            pass  # drop log rather than blocking the request

    def _worker(self):
        while not self._stop_event.is_set():
            batch = []
            try:
                # Block until at least one record arrives
                record = self._queue.get(timeout=self._flush_interval)
                batch.append(record)
            except queue.Empty:
                continue

            # Drain up to max_batch
            while len(batch) < self._max_batch:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break

            self._flush(batch)

    def _flush(self, batch: list[logging.LogRecord]):
        try:
            client = self._get_client()
            for record in batch:
                doc = self._format_record(record)
                client.index(index=self._index, document=doc)
        except Exception as exc:
            import sys
            print(f"[ElasticsearchHandler] flush failed ({len(batch)} records dropped): {exc}", file=sys.stderr)

    def _format_record(self, record: logging.LogRecord) -> dict:
        doc = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge structured extra fields (request_id, tx_id, etc.)
        for key in ("request_id", "user_id", "tx_id", "client_ip",
                     "document_type", "side", "step",
                     "ocr_text_count", "extracted_fields", "score",
                     "result", "detail", "error", "duration_ms",
                     "frames_analyzed", "frames_with_face", "face_presence_ratio",
                     "avg_face_ratio", "avg_blur_score", "liveness_score"):
            val = getattr(record, key, None)
            if val is not None:
                doc[key] = val
        return doc

    def close(self):
        self._stop_event.set()
        self._thread.join(timeout=10)
        super().close()
