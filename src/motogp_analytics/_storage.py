"""Canonical session artifact persistence and discovery."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from ._contracts import ParsedSession, _event_code


def save_session(parsed: ParsedSession, data_root: str | Path = "data") -> Path:
    """Atomically replace the four canonical artifacts for one parsed session."""

    event = _event_code(parsed.event)
    destination = (
        Path(data_root)
        / "processed"
        / f"year={parsed.year}"
        / f"event={event}"
        / f"session={parsed.session}"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{parsed.session}-", dir=destination.parent))
    try:
        parsed.laps.to_parquet(temporary / "laps.parquet", index=False)
        parsed.runs.to_parquet(temporary / "runs.parquet", index=False)
        parsed.partials.to_parquet(temporary / "partials.parquet", index=False)
        metadata = {
            "year": parsed.year,
            "event": parsed.event,
            "session": parsed.session,
            "observed_session": parsed.observed_session,
            "source_path": str(parsed.source_path),
            "source_sha256": parsed.source_sha256,
            "page_count": parsed.page_count,
            "generated_at": datetime.now(UTC).isoformat(),
            "quality": parsed.quality,
        }
        (temporary / "session.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        backup: Path | None = None
        if destination.exists():
            backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
            os.replace(destination, backup)
        try:
            os.replace(temporary, destination)
        except Exception:
            if backup is not None:
                os.replace(backup, destination)
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return destination


def load_laps(session_directory: str | Path) -> pd.DataFrame:
    """Load session laps through DuckDB in stable display order."""

    path = Path(session_directory) / "laps.parquet"
    if not path.is_file():
        raise FileNotFoundError(path)
    with duckdb.connect() as connection:
        return connection.execute(
            "SELECT * FROM read_parquet(?) ORDER BY position, lap", [str(path)]
        ).fetch_df()


def load_session_metadata(session_directory: str | Path) -> dict[str, Any]:
    """Load the persisted provenance and quality report for one session."""

    path = Path(session_directory) / "session.json"
    return json.loads(path.read_text(encoding="utf-8"))


def discover_sessions(data_root: str | Path = "data") -> list[Path]:
    """Find processed sessions that have the artifacts required by current readers."""

    candidates = Path(data_root).glob("processed/year=*/event=*/session=*")
    return sorted(
        path
        for path in candidates
        if path.is_dir() and (path / "laps.parquet").is_file() and (path / "session.json").is_file()
    )
