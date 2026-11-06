from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any


def make_event_id(event_type: str, payload: dict[str, Any]) -> str:
    identity = {
        "event_type": event_type,
        "msm_id": payload.get("msm_id"),
        "prb_id": payload.get("prb_id") or payload.get("id"),
        "timestamp": payload.get("timestamp"),
        "event": payload.get("event") or payload.get("type"),
    }
    raw = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def normalize_ping(payload: dict[str, Any], source_mode: str) -> dict[str, Any]:
    raw_results = payload.get("result") or []
    rtts = [item["rtt"] for item in raw_results if isinstance(item, dict) and isinstance(item.get("rtt"), (int, float)) and math.isfinite(item['rtt']) and item['rtt'] >= 0]
    sent = payload.get("sent") if payload.get("sent") is not None else len(raw_results)
    received = payload.get("rcvd") if payload.get("rcvd") is not None else len(rtts)
    # Preserve invalid packet fields for validation instead of throwing out of
    # the per-message handler and reconnecting the entire stream.
    if type(sent) is not int or type(received) is not int:
        raise ValueError('INVALID_PACKET_COUNTS')
    loss_pct = round((sent - received) / sent * 100, 4) if sent else 100.0
    event = {
        "schema_version": 1,
        "event_type": "ping_result",
        "source": "ripe_atlas",
        "source_mode": source_mode,
        "msm_id": payload.get("msm_id"),
        "prb_id": payload.get("prb_id"),
        "timestamp": payload.get("timestamp"),
        "af": payload.get("af"),
        "sent": sent,
        "rcvd": received,
        "loss_pct": loss_pct,
        "rtt_min": payload.get("min") if payload.get("min") not in (None, -1) else (min(rtts) if rtts else None),
        "rtt_avg": payload.get("avg") if payload.get("avg") not in (None, -1) else (sum(rtts) / len(rtts) if rtts else None),
        "rtt_max": payload.get("max") if payload.get("max") not in (None, -1) else (max(rtts) if rtts else None),
        "dst_name": payload.get("dst_name"),
        "dst_addr": payload.get("dst_addr"),
        "src_addr": payload.get("from"),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    event["event_id"] = make_event_id("ping_result", event)
    if received == 0:
        event.update(rtt_min=None, rtt_avg=None, rtt_max=None)
    return event


def normalize_probe_status(payload: dict[str, Any]) -> dict[str, Any]:
    event = {
        "schema_version": 1,
        "event_type": "probe_status",
        "source": "ripe_atlas",
        "source_mode": "stream",
        "prb_id": payload.get("prb_id") or payload.get("id"),
        "timestamp": payload.get("timestamp") or int(datetime.now(timezone.utc).timestamp()),
        "event": payload.get("event") or payload.get("type") or "unknown",
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    event["event_id"] = make_event_id("probe_status", event)
    return event


def validate_minimum(event: dict[str, Any]) -> tuple[bool, str | None]:
    if not isinstance(event.get("prb_id"), int) or event["prb_id"] <= 0:
        return False, "INVALID_PROBE_ID"
    if not isinstance(event.get("timestamp"), int) or event["timestamp"] <= 0:
        return False, "INVALID_TIMESTAMP"
    if event["event_type"] == "ping_result":
        if not isinstance(event.get("msm_id"), int):
            return False, "INVALID_MEASUREMENT_ID"
        if event.get("sent", 0) <= 0:
            return False, "INVALID_SENT"
        if not 0 <= event.get("rcvd", -1) <= event["sent"]:
            return False, "INVALID_RECEIVED"
        if not 0 <= event.get("loss_pct", -1) <= 100:
            return False, "INVALID_LOSS"
        if event.get('af') not in (4, 6):
            return False, 'INVALID_AF'
        if abs(event['loss_pct'] - 100*(event['sent']-event['rcvd'])/event['sent']) > .001:
            return False, 'INCONSISTENT_LOSS'
        rtts=[event.get(k) for k in ('rtt_min','rtt_avg','rtt_max')]
        if any(v is not None and (type(v) not in (int,float) or not math.isfinite(v) or not 0 <= v < 10000) for v in rtts):
            return False, 'INVALID_RTT'
        if event['rcvd']==0 and any(v is not None for v in rtts):
            return False, 'RTT_WITHOUT_REPLY'
        if event['rcvd']>0 and any(v is None for v in rtts):
            return False, 'MISSING_RTT'
        if all(v is not None for v in rtts) and not rtts[0] <= rtts[1] <= rtts[2]:
            return False, 'INCONSISTENT_RTT'
    elif event.get('event_type')=='probe_status':
        if str(event.get('event','')).lower() not in ('connect','connected','disconnect','disconnected','down'):
            return False,'INVALID_PROBE_STATUS'
    return True, None
