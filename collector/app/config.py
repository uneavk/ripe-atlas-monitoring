from __future__ import annotations

import os
from dataclasses import dataclass


def _csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    country: str = os.getenv("COUNTRY", "UA")
    measurement_ids: tuple[int, ...] = _csv_ints(os.getenv("MEASUREMENT_IDS", "1001,2001,1004,2004"))
    backfill_minutes: int = int(os.getenv("BACKFILL_MINUTES", "60"))
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
    postgres_dsn: str = os.getenv("POSTGRES_DSN", "")
    checkpoint_file: str = os.getenv("CHECKPOINT_FILE", "state/checkpoints.json")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    rest_base: str = "https://atlas.ripe.net/api/v2"
    stream_url: str = "wss://atlas-stream.ripe.net/stream/?client=stp-lab-ua-v2"
    reconnect_min_seconds: int = 5
    reconnect_max_seconds: int = 60


settings = Settings()
