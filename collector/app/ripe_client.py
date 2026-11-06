from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterable
from typing import Any

import requests
import websocket

logger = logging.getLogger(__name__)


class RipeAtlasClient:
    def __init__(self, rest_base: str, stream_url: str, country: str, measurement_ids: tuple[int, ...]) -> None:
        self.rest_base = rest_base
        self.stream_url = stream_url
        self.country = country
        self.measurement_ids = measurement_ids
        self.session = requests.Session()

    def fetch_probes(self) -> list[dict[str, Any]]:
        url: str | None = f"{self.rest_base}/probes/"
        params: dict[str, Any] | None = {"country_code": self.country, "page_size": 500, "format": "json"}
        probes: list[dict[str, Any]] = []
        while url:
            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            for probe in data.get("results", []):
                coordinates = (probe.get("geometry") or {}).get("coordinates") or [None, None]
                probes.append({
                    "schema_version": 1,
                    "event_type": "probe_metadata",
                    "prb_id": probe.get("id"),
                    "asn_v4": probe.get("asn_v4"),
                    "asn_v6": probe.get("asn_v6"),
                    "country": probe.get("country_code"),
                    "longitude": coordinates[0],
                    "latitude": coordinates[1],
                    "status": (probe.get('status') or {}).get('name') or probe.get("status_name") or "",
                    "address_v4": probe.get("address_v4"),
                })
            url, params = data.get("next"), None
        logger.info("probes_fetched", extra={"event": "probes_fetched", "count": len(probes)})
        self.probe_ids=tuple(p['prb_id'] for p in probes)
        return probes

    def validate_measurements(self):
        for msm in self.measurement_ids:
            response=self.session.get(f'{self.rest_base}/measurements/{msm}/',timeout=30)
            response.raise_for_status();definition=response.json()
            if definition.get('type')!='ping' or definition.get('status',{}).get('name')!='Ongoing' or definition.get('af') not in (4,6):
                raise ValueError(f'Inactive or unsupported measurement: {msm}')
            logger.info('measurement_verified',extra={'event':'measurement_verified','msm_id':msm})

    def backfill(self, msm_id: int, start: int, stop: int) -> Iterable[dict[str, Any]]:
        # Keep requests small enough for built-in global measurements.
        for window_start in range(start, stop, 300):
            response = self.session.get(
                f"{self.rest_base}/measurements/{msm_id}/results/",
                params={"start": window_start, "stop": min(window_start + 300, stop), "format": "json", **({'probe_ids':','.join(map(str,self.probe_ids))} if getattr(self,'probe_ids',None) else {})},
                timeout=60,
            )
            response.raise_for_status()
            yield from response.json()

    def stream(self, on_message: Callable[[str, dict[str, Any]], None]) -> None:
        ws = websocket.WebSocket()
        ws.connect(self.stream_url, timeout=45)
        try:
            for msm_id in self.measurement_ids:
                ws.send(json.dumps(["atlas_subscribe", {"streamType": "result", "msm": msm_id}]))
            ws.send(json.dumps(["atlas_subscribe", {"streamType": "probestatus"}]))
            logger.info("websocket_connected", extra={"event": "websocket_connected"})
            for raw in ws:
                try:
                    message = json.loads(raw)
                except (TypeError, ValueError):
                    on_message('invalid_event', {'reason':'JSON_DECODE','raw':str(raw)[:4096]})
                    continue
                if not isinstance(message, list) or len(message) != 2 or not isinstance(message[1], dict):
                    on_message('invalid_event', {'reason':'EXPECTED_PAIR','raw':str(raw)[:4096]})
                    continue
                on_message(message[0], message[1])
        finally:
            ws.close()
            logger.warning("websocket_disconnected", extra={"event": "websocket_disconnected"})
