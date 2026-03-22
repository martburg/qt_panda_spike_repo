from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class PickLog:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            **record,
        }
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
