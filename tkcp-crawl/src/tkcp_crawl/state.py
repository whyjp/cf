"""Resume state — `data/state.json` 으로 last_page / total_seen 저장."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel


class PullState(BaseModel):
    schema_version: int = 1
    last_page: int = 0
    total_seen: int = 0
    started_at: str = ""
    completed_at: str = ""

    @classmethod
    def fresh(cls) -> "PullState":
        return cls(started_at=datetime.now(timezone.utc).isoformat())


def load(path: Path) -> PullState:
    if not path.exists():
        return PullState.fresh()
    try:
        return PullState.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return PullState.fresh()


def save(path: Path, state: PullState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
