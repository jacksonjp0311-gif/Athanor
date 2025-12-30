from __future__ import annotations
import json
from typing import Any, Dict

def log_jsonl(path: str, row: Dict[str, Any]):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(row) + '\\n')