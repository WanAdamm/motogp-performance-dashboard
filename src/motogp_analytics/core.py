"""Public pipeline facade and command-line orchestration.

Implementations live in focused private modules. Consumers should import this facade or the
package root so pipeline boundaries remain stable as internals evolve.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ._acquisition import analysis_url as analysis_url
from ._acquisition import download_pdf as download_pdf
from ._analytics import SUMMARY_COLUMNS as SUMMARY_COLUMNS
from ._analytics import format_time as format_time
from ._analytics import matched_lap_deltas as matched_lap_deltas
from ._analytics import pace_leaders as pace_leaders
from ._analytics import rider_summary as rider_summary
from ._analytics import sector_deficits as sector_deficits
from ._analytics import select_scope as select_scope
from ._classification import LAP_SCHEMA as LAP_SCHEMA
from ._contracts import EVENT_RE as EVENT_RE
from ._contracts import LAP_COLUMNS as LAP_COLUMNS
from ._contracts import PARTIAL_COLUMNS as PARTIAL_COLUMNS
from ._contracts import RUN_COLUMNS as RUN_COLUMNS
from ._contracts import SECTOR_TOLERANCE_SECONDS as SECTOR_TOLERANCE_SECONDS
from ._contracts import SUPPORTED_SESSIONS as SUPPORTED_SESSIONS
from ._contracts import ParsedSession as ParsedSession
from ._contracts import _event_code as _event_code
from ._contracts import _session_code as _session_code
from ._parsing import COLUMN_SPLIT as COLUMN_SPLIT
from ._parsing import EVENT_TITLE_MARKERS as EVENT_TITLE_MARKERS
from ._parsing import POSITION_RE as POSITION_RE
from ._parsing import RIGHT_OFFSET as RIGHT_OFFSET
from ._parsing import SESSION_TITLES as SESSION_TITLES
from ._parsing import TIME_RE as TIME_RE
from ._parsing import TYRE_RE as TYRE_RE
from ._parsing import Word as Word
from ._parsing import detect_session as detect_session
from ._parsing import parse_pdf as parse_pdf
from ._parsing import parse_time as parse_time
from ._storage import discover_sessions as discover_sessions
from ._storage import load_laps as load_laps
from ._storage import load_session_metadata as load_session_metadata
from ._storage import save_session as save_session


def ingest(
    *,
    year: int,
    event: str,
    session: str,
    pdf_path: str | Path | None = None,
    data_root: str | Path = "data",
    force_download: bool = False,
) -> Path:
    """Acquire or open, parse, and persist one session through the pipeline."""

    root = Path(data_root)
    source = (
        Path(pdf_path)
        if pdf_path
        else download_pdf(year, event, session, root, force=force_download)
    )
    parsed = parse_pdf(source, year=year, event=event, session=session)
    return save_session(parsed, root)


def main(argv: list[str] | None = None) -> int:
    """Run the ingestion or rider-summary command."""

    parser = argparse.ArgumentParser(prog="motogp-analytics")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest_command = commands.add_parser("ingest", help="Parse and validate one session")
    ingest_command.add_argument("--year", type=int, required=True)
    ingest_command.add_argument("--event", required=True)
    ingest_command.add_argument("--session", required=True, choices=sorted(SUPPORTED_SESSIONS))
    ingest_command.add_argument("--pdf", type=Path)
    ingest_command.add_argument("--data-root", type=Path, default=Path("data"))
    ingest_command.add_argument("--force-download", action="store_true")

    summary_command = commands.add_parser("summary", help="Show rider pace summary")
    summary_command.add_argument("session_directory", type=Path)
    summary_command.add_argument("--scope", choices=["clean", "raw"], default="clean")

    args = parser.parse_args(argv)
    if args.command == "ingest":
        destination = ingest(
            year=args.year,
            event=args.event,
            session=args.session,
            pdf_path=args.pdf,
            data_root=args.data_root,
            force_download=args.force_download,
        )
        print(destination)
        print((destination / "session.json").read_text(encoding="utf-8"))
        return 0
    laps = load_laps(args.session_directory)
    print(rider_summary(laps, scope=args.scope).to_string(index=False))
    return 0
