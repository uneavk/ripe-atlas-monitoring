from __future__ import annotations
import json,time
from pathlib import Path
class CheckpointStore:
    """Collector position persists in its Docker state volume, without PostgreSQL."""
    def __init__(self,dsn,fallback_file):
        self.path=Path(fallback_file);self.path.parent.mkdir(parents=True,exist_ok=True);self._last_flush=0.0
        try:self._cache=json.loads(self.path.read_text(encoding='utf-8'))
        except (FileNotFoundError,ValueError):self._cache={}
    def get(self,msm_id):
        value=self._cache.get(str(msm_id));return int(value) if value is not None else None
    def set(self,msm_id,timestamp):
        key=str(msm_id);self._cache[key]=max(int(timestamp),int(self._cache.get(key,0)))
        if time.monotonic()-self._last_flush>=5:self.flush()
    def flush(self):
        temporary=self.path.with_suffix('.tmp');temporary.write_text(json.dumps(self._cache),encoding='utf-8');temporary.replace(self.path);self._last_flush=time.monotonic()
