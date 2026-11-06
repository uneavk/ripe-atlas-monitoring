from __future__ import annotations

import logging
import signal
import time
import hashlib
import json
from datetime import datetime, timezone

from .checkpoint import CheckpointStore
from .config import settings
from .kafka_io import ReliableProducer
from .logging_config import configure_logging
from .models import normalize_ping, normalize_probe_status, validate_minimum
from .ripe_client import RipeAtlasClient

logger = logging.getLogger(__name__)
running = True


def stop(*_: object) -> None:
    global running
    running = False


def main() -> None:
    configure_logging(settings.log_level)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    producer = ReliableProducer(settings.kafka_bootstrap_servers)
    checkpoint = CheckpointStore(settings.postgres_dsn, settings.checkpoint_file)
    client = RipeAtlasClient(settings.rest_base, settings.stream_url, settings.country, settings.measurement_ids)

    probes = client.fetch_probes()
    client.validate_measurements()
    probe_ids = {item["prb_id"] for item in probes if item.get("prb_id")}
    for probe in probes:
        probe["event_id"] = f"probe-{probe['prb_id']}"
        producer.publish("ripe.probes", probe)

    def reject(reason, payload, stage='collector'):
        identity=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
        producer.publish('ripe.dead_letter', {'schema_version':1,'event_id':identity,'stage':stage,'reason':reason,'payload':payload,'received_at':datetime.now(timezone.utc).isoformat()})

    def refresh_probes():
        updated=client.fetch_probes()
        for probe in updated:
            probe['event_id']=f"probe-{probe['prb_id']}"
            producer.publish('ripe.probes',probe)
        probe_ids.clear();probe_ids.update(p['prb_id'] for p in updated)

    def publish_ping(payload: dict, source_mode: str) -> None:
        if payload.get("prb_id") not in probe_ids:
            return
        try:
            event = normalize_ping(payload, source_mode)
        except (ValueError,TypeError,KeyError,OverflowError) as error:
            reject('NORMALIZATION_'+type(error).__name__,payload)
            return
        valid, reason = validate_minimum(event)
        if not valid:
            reject(reason,event)
            return
        producer.publish("ripe.raw", event)

    def perform_backfill() -> None:
        stop_ts = int(datetime.now(timezone.utc).timestamp())
        for msm_id in settings.measurement_ids:
            last = checkpoint.get(msm_id)
            horizon = stop_ts - settings.backfill_minutes * 60
            # The checkpoint is a COMPLETED REST range, never the greatest
            # observed event. Replay overlaps boundaries; the sink deduplicates.
            start_ts = max(last - 600, horizon) if last else horizon
            if last and last + 1 < horizon:
                logger.warning("backfill_gap_outside_window", extra={"event": "backfill_gap_outside_window", "msm_id": msm_id, "reason": "Older history requires a separate historical import"})
            if start_ts >= stop_ts:
                continue
            logger.info("backfill_started", extra={"event": "backfill_started", "msm_id": msm_id})
            count = 0
            try:
                for payload in client.backfill(msm_id, start_ts, stop_ts):
                    publish_ping(payload, "backfill")
                    count += 1
                checkpoint.set(msm_id,stop_ts)
                checkpoint.flush()
            except Exception:
                logger.exception("backfill_failed", extra={"event": "backfill_failed", "msm_id": msm_id})
                continue
            logger.info("backfill_completed", extra={"event": "backfill_completed", "msm_id": msm_id, "count": count})

    perform_backfill()
    delay = settings.reconnect_min_seconds
    last_refresh=time.monotonic()
    last_reconcile=time.monotonic()
    try:
        while running:
            try:
                def on_message(message_type: str, payload: dict) -> None:
                    nonlocal last_refresh,last_reconcile
                    if time.monotonic()-last_refresh>=3600:
                        refresh_probes();last_refresh=time.monotonic()
                    # Periodic reconciliation also repairs RIPE's documented
                    # stream drop warnings without blocking this socket on REST.
                    if time.monotonic()-last_reconcile>=600:
                        raise ConnectionError('scheduled_stream_reconciliation')
                    if message_type == "atlas_result":
                        publish_ping(payload, "stream")
                    elif message_type == "atlas_probestatus":
                        probe_id = payload.get("prb_id") or payload.get("id")
                        if probe_id in probe_ids:
                            event = normalize_probe_status(payload)
                            valid, reason = validate_minimum(event)
                            producer.publish("ripe.probe_status" if valid else "ripe.dead_letter", event if valid else {"event_id": event["event_id"], "prb_id": probe_id, "reason": reason, "payload": event})
                    elif message_type == "atlas_error":
                        reject('ATLAS_STREAM_ERROR',payload,'ripe_stream')
                        raise ConnectionError('atlas_stream_requires_reconciliation')
                    elif message_type == 'invalid_event':
                        reject(payload['reason'],payload,'websocket')

                client.stream(on_message)
                delay = settings.reconnect_min_seconds
            except Exception:
                logger.exception("stream_cycle_failed", extra={"event": "stream_cycle_failed", "attempt": delay})
                if not running:
                    break
                time.sleep(delay)
                perform_backfill()
                last_reconcile=time.monotonic()
                delay = min(delay * 2, settings.reconnect_max_seconds)
    finally:
        checkpoint.flush()
        producer.close()


if __name__ == "__main__":
    main()
