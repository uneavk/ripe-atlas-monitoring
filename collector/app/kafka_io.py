from __future__ import annotations

import json
import logging
import time
from typing import Any

from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


class ReliableProducer:
    def __init__(self, bootstrap_servers: str) -> None:
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers.split(","),
            acks="all",
            retries=10,
            retry_backoff_ms=1000,
            # publish waits for each ACK, so linger cannot batch here and only
            # adds 50 ms to every event during recovery.
            linger_ms=0,
            compression_type="gzip",
            key_serializer=lambda value: str(value).encode("utf-8"),
            value_serializer=lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        )

    def publish(self, topic: str, event: dict[str, Any], max_attempts: int = 5) -> None:
        key = event.get("prb_id") or event.get("event_id")
        for attempt in range(1, max_attempts + 1):
            try:
                future = self.producer.send(topic, key=key, value=event)
                future.get(timeout=30)
                logger.info("kafka_publish_ok", extra={"event": "kafka_publish_ok", "event_id": event.get("event_id"), "topic": topic, "attempt": attempt})
                return
            except KafkaError:
                logger.exception("kafka_publish_failed", extra={"event": "kafka_publish_failed", "event_id": event.get("event_id"), "topic": topic, "attempt": attempt})
                if attempt == max_attempts:
                    raise
                time.sleep(min(2 ** attempt, 15))

    def close(self) -> None:
        self.producer.flush(timeout=30)
        self.producer.close(timeout=30)
