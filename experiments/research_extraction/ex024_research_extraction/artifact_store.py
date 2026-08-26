from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_completed_run(path: Path, payload: dict[str, Any]) -> None:
    """Write one immutable research run; never overwrite a completed run."""
    if path.exists():
        raise FileExistsError(f"completed research run already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
