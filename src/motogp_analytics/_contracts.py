"""Shared pipeline data contracts and identifier validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

SUPPORTED_SESSIONS = {"FP1", "FP2", "PR", "Q1", "Q2", "WUP", "SPR", "RAC"}
EVENT_RE = re.compile(r"^[A-Z0-9]{3}$")
SECTOR_TOLERANCE_SECONDS = 0.003

LAP_COLUMNS = [
    "year",
    "event",
    "session",
    "rider_number",
    "rider",
    "team",
    "constructor",
    "nationality",
    "position",
    "declared_runs",
    "declared_total_laps",
    "declared_full_laps",
    "declared_valid_laps",
    "run",
    "lap",
    "lap_time_seconds",
    "t1",
    "t2",
    "t3",
    "t4",
    "speed",
    "pit_crossing",
    "lap_cancelled",
    "t1_cancelled",
    "t2_cancelled",
    "t3_cancelled",
    "t4_cancelled",
    "source_page",
    "source_column",
    "source_y",
]
RUN_COLUMNS = [
    "year",
    "event",
    "session",
    "rider_number",
    "rider",
    "run",
    "front_tyre",
    "rear_tyre",
    "front_tyre_new",
    "rear_tyre_new",
    "front_tyre_laps_at_start",
    "rear_tyre_laps_at_start",
    "source_page",
    "source_column",
]
PARTIAL_COLUMNS = [
    "year",
    "event",
    "session",
    "rider_number",
    "rider",
    "run",
    "row_kind",
    "t1",
    "t2",
    "t3",
    "t4",
    "speed",
    "pit_crossing",
    "t1_cancelled",
    "t2_cancelled",
    "t3_cancelled",
    "t4_cancelled",
    "source_page",
    "source_column",
    "source_y",
]


@dataclass
class ParsedSession:
    """Validated tables and provenance produced from one timing PDF."""

    year: int
    event: str
    session: str
    observed_session: str
    source_path: Path
    source_sha256: str
    page_count: int
    laps: pd.DataFrame
    runs: pd.DataFrame
    partials: pd.DataFrame
    quality: dict[str, Any]


def _session_code(session: str) -> str:
    code = session.upper()
    if code not in SUPPORTED_SESSIONS:
        raise ValueError(f"Unsupported session {session!r}")
    return code


def _event_code(event: str) -> str:
    code = event.upper()
    if not EVENT_RE.fullmatch(code):
        raise ValueError(f"Invalid event code {event!r}; expected three letters or digits")
    return code
