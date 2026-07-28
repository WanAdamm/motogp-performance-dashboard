"""MotoGP timing PDF ingestion and analytics."""

from .core import (
    ParsedSession,
    analysis_url,
    discover_sessions,
    format_time,
    ingest,
    load_laps,
    load_session_metadata,
    matched_lap_deltas,
    pace_leaders,
    parse_pdf,
    parse_time,
    rider_summary,
    sector_deficits,
    select_scope,
)

__all__ = [
    "ParsedSession",
    "analysis_url",
    "discover_sessions",
    "format_time",
    "ingest",
    "load_laps",
    "load_session_metadata",
    "matched_lap_deltas",
    "pace_leaders",
    "parse_pdf",
    "parse_time",
    "rider_summary",
    "sector_deficits",
    "select_scope",
]
