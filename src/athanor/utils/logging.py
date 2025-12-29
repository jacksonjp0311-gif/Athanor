from __future__ import annotations
import json
from datetime import datetime, timezone

def event(kind: str, **kwargs):
    row = { 'ts': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'), 'kind': kind }
    row.update(kwargs)
    return json.dumps(row)
