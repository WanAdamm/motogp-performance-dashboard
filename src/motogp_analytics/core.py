from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import fitz
import httpx
import pandas as pd
import pandera.pandas as pa

SUPPORTED_SESSIONS = {"FP1", "FP2", "PR", "Q1", "Q2", "WUP", "SPR", "RAC"}
SESSION_TITLES = (
    ("FREE PRACTICE NR. 1", "FP1"),
    ("FREE PRACTICE NR. 2", "FP2"),
    ("TISSOT SPRINT", "SPR"),
    ("WARM UP", "WUP"),
    ("PRACTICE", "PR"),
    ("RACE", "RAC"),
    ("QUALIFYING NR. 1", "Q1"),
    ("QUALIFYING NR. 2", "Q2"),
)
TIME_RE = re.compile(r"^(?:\d+')?\d{1,2}\.\d{3}$")
POSITION_RE = re.compile(r"^(\d+)(?:st|nd|rd|th)$")
EVENT_RE = re.compile(r"^[A-Z0-9]{3}$")
TYRE_RE = re.compile(r"^(?:Slick|Wet)-")
EVENT_TITLE_MARKERS = {
    "SPA": "GRAND PRIX OF SPAIN",
    "FRA": "GRAND PRIX OF FRANCE",
}
COLUMN_SPLIT = 297.5
RIGHT_OFFSET = 272.2
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
SUMMARY_COLUMNS = [
    "rider_number",
    "rider",
    "team",
    "constructor",
    "laps",
    "fastest",
    "mean",
    "median",
    "std_dev",
    "q1",
    "q3",
    "iqr",
    "top_speed",
    "best_t1",
    "best_t2",
    "best_t3",
    "best_t4",
    "median_t1",
    "median_t2",
    "median_t3",
    "median_t4",
    "theoretical_reference",
    "theoretical_best",
    "potential_lost",
]

LAP_SCHEMA = pa.DataFrameSchema(
    {
        "year": pa.Column(int, pa.Check.ge(2000), coerce=True),
        "event": pa.Column(str),
        "session": pa.Column(str, pa.Check.isin(sorted(SUPPORTED_SESSIONS))),
        "rider_number": pa.Column(int, pa.Check.ge(0), coerce=True),
        "rider": pa.Column(str),
        "run": pa.Column(int, pa.Check.ge(1), coerce=True),
        "lap": pa.Column(int, pa.Check.ge(1), coerce=True),
        "lap_time_seconds": pa.Column(float, pa.Check.gt(0), coerce=True),
        "t1": pa.Column(float, pa.Check.gt(0), nullable=True, coerce=True),
        "t2": pa.Column(float, pa.Check.gt(0), nullable=True, coerce=True),
        "t3": pa.Column(float, pa.Check.gt(0), nullable=True, coerce=True),
        "t4": pa.Column(float, pa.Check.gt(0), nullable=True, coerce=True),
        "speed": pa.Column(float, pa.Check.gt(0), nullable=True, coerce=True),
    },
    unique=["year", "event", "session", "rider_number", "lap"],
    strict=False,
)

Word = tuple[float, float, float, float, str]


@dataclass
class ParsedSession:
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


def analysis_url(year: int, event: str, session: str) -> str:
    session = _session_code(session)
    event = _event_code(event)
    return (
        f"https://resources.motogp.com/files/results/{year}/{event}/MotoGP/{session}/Analysis.pdf"
    )


def download_pdf(
    year: int,
    event: str,
    session: str,
    data_root: Path = Path("data"),
    *,
    force: bool = False,
) -> Path:
    session = _session_code(session)
    event = _event_code(event)
    target = data_root / "raw" / str(year) / event / session / "Analysis.pdf"
    if target.exists() and not force:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        response = client.get(analysis_url(year, event, session))
        response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError("Downloaded response is not a PDF")
    temporary = target.with_suffix(".pdf.tmp")
    temporary.write_bytes(response.content)
    os.replace(temporary, target)
    return target


def parse_time(value: str) -> float:
    if not TIME_RE.fullmatch(value):
        raise ValueError(f"Invalid timing value: {value!r}")
    if "'" not in value:
        return float(value)
    minutes, seconds = value.split("'", 1)
    return int(minutes) * 60 + float(seconds)


def detect_session(document: fitz.Document) -> str:
    text = document[0].get_text().upper()
    for title, code in SESSION_TITLES:
        if title in text:
            return code
    raise ValueError("Could not identify session from PDF title")


def parse_pdf(
    pdf_path: str | Path,
    *,
    year: int,
    event: str,
    session: str,
    sector_tolerance_seconds: float = SECTOR_TOLERANCE_SECONDS,
) -> ParsedSession:
    path = Path(pdf_path)
    session = _session_code(session)
    event = _event_code(event)
    if not path.is_file():
        raise FileNotFoundError(path)
    if sector_tolerance_seconds < 0:
        raise ValueError("Sector tolerance must be non-negative")

    source_bytes = path.read_bytes()
    document = fitz.open(stream=source_bytes, filetype="pdf")
    first_page_text = document[0].get_text().upper()
    if not re.search(rf"\b{year}\b", first_page_text):
        document.close()
        raise ValueError(f"Year mismatch: expected {year}")
    event_marker = EVENT_TITLE_MARKERS.get(event)
    if event_marker and event_marker not in first_page_text:
        document.close()
        raise ValueError(f"Event mismatch: expected {event}")
    observed_session = detect_session(document)
    if observed_session != session:
        document.close()
        raise ValueError(f"Session mismatch: expected {session}, PDF contains {observed_session}")

    riders: dict[int, dict[str, Any]] = {}
    lap_records: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []
    partial_records: list[dict[str, Any]] = []
    current_rider: dict[str, Any] | None = None
    current_run: int | None = None

    for page_number, page in enumerate(document, start=1):
        for column in ("left", "right"):
            words = _column_words(page, column)
            rows = _rows(words)
            row_positions = sorted(rows)
            for y in row_positions:
                row = rows[y]
                position_word = next(
                    (word for word in row if _center(word) < 65 and POSITION_RE.fullmatch(word[4])),
                    None,
                )
                has_rider_number = any(
                    word[4].isdigit()
                    and 60 <= _center(word) <= 90
                    and position_word
                    and abs(word[1] - position_word[1]) <= 4
                    for word in words
                )
                if position_word and has_rider_number:
                    current_rider = _parse_rider_header(words, position_word)
                    current_rider.update(
                        {
                            "year": year,
                            "event": event,
                            "session": session,
                        }
                    )
                    riders[current_rider["rider_number"]] = current_rider
                    current_run = None
                    continue

                row_text = " ".join(word[4] for word in row)
                if current_rider and "Runs=" in row_text and "Valid" in row_text:
                    match = re.search(
                        r"Runs=(\d+).*Total\s+laps=(\d+).*Full\s+laps=(\d+).*"
                        r"Valid\s+laps=(\d+)",
                        row_text,
                    )
                    if match:
                        current_rider.update(
                            {
                                "declared_runs": int(match.group(1)),
                                "declared_total_laps": int(match.group(2)),
                                "declared_full_laps": int(match.group(3)),
                                "declared_valid_laps": int(match.group(4)),
                            }
                        )
                    continue

                if current_rider and _is_run_header(row):
                    current_run, run_record = _parse_run(
                        row,
                        words,
                        y,
                        current_rider,
                        page_number,
                        column,
                    )
                    run_records.append(run_record)
                    continue

                if not current_rider or current_run is None:
                    continue

                lap_record = _parse_lap_row(
                    row,
                    current_rider,
                    current_run,
                    page_number,
                    column,
                    y,
                )
                if lap_record:
                    lap_records.append(lap_record)
                    continue

                partial_record = _parse_partial_row(
                    row,
                    current_rider,
                    current_run,
                    page_number,
                    column,
                    y,
                )
                if partial_record:
                    partial_records.append(partial_record)

    document.close()
    laps = pd.DataFrame(lap_records, columns=LAP_COLUMNS)
    runs = pd.DataFrame(run_records, columns=RUN_COLUMNS)
    partials = pd.DataFrame(partial_records, columns=PARTIAL_COLUMNS)
    if laps.empty:
        raise ValueError("No numbered laps were detected")
    run_key = ["year", "event", "session", "rider_number", "run"]
    if runs.duplicated(run_key).any():
        raise ValueError("Duplicate run keys detected")
    known_runs = set(runs[run_key].itertuples(index=False, name=None))
    lap_runs = set(laps[run_key].itertuples(index=False, name=None))
    if unknown_runs := lap_runs - known_runs:
        raise ValueError(f"Laps reference missing runs: {sorted(unknown_runs)}")

    laps = _validate_and_classify(laps, session, sector_tolerance_seconds)
    quality = _quality_report(laps, runs, partials, riders, sector_tolerance_seconds)
    return ParsedSession(
        year=year,
        event=event,
        session=session,
        observed_session=observed_session,
        source_path=path.resolve(),
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        page_count=page_number,
        laps=laps,
        runs=runs,
        partials=partials,
        quality=quality,
    )


def ingest(
    *,
    year: int,
    event: str,
    session: str,
    pdf_path: str | Path | None = None,
    data_root: str | Path = "data",
    force_download: bool = False,
) -> Path:
    root = Path(data_root)
    source = (
        Path(pdf_path)
        if pdf_path
        else download_pdf(year, event, session, root, force=force_download)
    )
    parsed = parse_pdf(source, year=year, event=event, session=session)
    return save_session(parsed, root)


def save_session(parsed: ParsedSession, data_root: str | Path = "data") -> Path:
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
    path = Path(session_directory) / "laps.parquet"
    if not path.is_file():
        raise FileNotFoundError(path)
    with duckdb.connect() as connection:
        return connection.execute(
            "SELECT * FROM read_parquet(?) ORDER BY position, lap", [str(path)]
        ).fetch_df()


def rider_summary(laps: pd.DataFrame, *, scope: str = "clean") -> pd.DataFrame:
    selected = select_scope(laps, scope)
    if selected.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    rows: list[dict[str, Any]] = []
    for keys, rider_laps in selected.groupby(
        ["rider_number", "rider", "team", "constructor"], sort=False
    ):
        times = rider_laps["lap_time_seconds"].dropna()
        sector_laps = laps[
            (laps["rider_number"] == keys[0])
            & laps["official_valid"]
            & laps["sector_sum_ok"].fillna(False).astype(bool)
        ]
        if scope == "clean":
            sector_laps = sector_laps[sector_laps["classification"] == "CLEAN"]
        sectors = sector_laps[["t1", "t2", "t3", "t4"]]
        best_sectors = sectors.min()
        theoretical = round(best_sectors.sum(min_count=4), 3)
        theoretical_reference = sector_laps["lap_time_seconds"].min()
        q1 = times.quantile(0.25)
        q3 = times.quantile(0.75)
        rows.append(
            {
                "rider_number": keys[0],
                "rider": keys[1],
                "team": keys[2],
                "constructor": keys[3],
                "laps": len(times),
                "fastest": times.min(),
                "mean": times.mean(),
                "median": times.median(),
                "std_dev": times.std(ddof=1),
                "q1": q1,
                "q3": q3,
                "iqr": q3 - q1,
                "top_speed": rider_laps["speed"].max(),
                "best_t1": best_sectors["t1"],
                "best_t2": best_sectors["t2"],
                "best_t3": best_sectors["t3"],
                "best_t4": best_sectors["t4"],
                "median_t1": sectors["t1"].median(),
                "median_t2": sectors["t2"].median(),
                "median_t3": sectors["t3"].median(),
                "median_t4": sectors["t4"].median(),
                "theoretical_reference": theoretical_reference,
                "theoretical_best": theoretical,
                "potential_lost": round(theoretical_reference - theoretical, 3),
            }
        )
    return (
        pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
        .sort_values("median", na_position="last")
        .reset_index(drop=True)
    )


def select_scope(laps: pd.DataFrame, scope: str) -> pd.DataFrame:
    if scope == "clean":
        return laps[laps["classification"] == "CLEAN"].copy()
    if scope == "raw":
        return laps[laps["lap_time_seconds"].notna()].copy()
    raise ValueError("Scope must be 'clean' or 'raw'")


def format_time(seconds: float | None) -> str:
    if seconds is None or pd.isna(seconds):
        return "—"
    value = round(float(seconds), 3)
    sign = "-" if value < 0 else ""
    minutes, remainder = divmod(abs(value), 60)
    formatted = f"{int(minutes)}'{remainder:06.3f}" if minutes else f"{remainder:.3f}"
    return f"{sign}{formatted}"


def discover_sessions(data_root: str | Path = "data") -> list[Path]:
    candidates = Path(data_root).glob("processed/year=*/event=*/session=*")
    return sorted(
        path
        for path in candidates
        if path.is_dir() and (path / "laps.parquet").is_file() and (path / "session.json").is_file()
    )


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


def _column_words(page: fitz.Page, column: str) -> list[Word]:
    words: list[Word] = []
    for raw in page.get_text("words"):
        x0, y0, x1, y1, text = raw[:5]
        is_left = (x0 + x1) / 2 < COLUMN_SPLIT
        if (column == "left") != is_left:
            continue
        offset = 0 if is_left else RIGHT_OFFSET
        words.append((x0 - offset, y0, x1 - offset, y1, text))
    return words


def _rows(words: list[Word]) -> dict[float, list[Word]]:
    rows: dict[float, list[Word]] = {}
    current_y: float | None = None
    for word in sorted(words, key=lambda value: (value[1], value[0])):
        if current_y is None or abs(word[1] - current_y) > 0.5:
            current_y = word[1]
            rows[current_y] = []
        rows[current_y].append(word)
    for row in rows.values():
        row.sort(key=lambda word: word[0])
    return rows


def _center(word: Word) -> float:
    return (word[0] + word[2]) / 2


def _parse_rider_header(words: list[Word], position_word: Word) -> dict[str, Any]:
    position_y = position_word[1]
    number_words = [
        word
        for word in words
        if 60 <= _center(word) <= 90 and word[4].isdigit() and abs(word[1] - position_y) <= 4
    ]
    name_rows = sorted(
        {
            word[1]
            for word in words
            if 88 <= word[0] < 202 and position_y - 5 <= word[1] <= position_y + 3
        }
    )
    if not number_words or not name_rows:
        raise ValueError(f"Incomplete rider header near y={position_y:.1f}")
    name_y = name_rows[0]
    name = " ".join(
        word[4]
        for word in sorted(words, key=lambda value: value[0])
        if abs(word[1] - name_y) < 0.2 and 88 <= word[0] < 202
    )
    constructor = " ".join(
        word[4]
        for word in sorted(words, key=lambda value: value[0])
        if abs(word[1] - name_y) < 0.2 and 202 <= word[0] < 260
    )
    nationality = " ".join(
        word[4]
        for word in sorted(words, key=lambda value: value[0])
        if abs(word[1] - name_y) < 0.2 and 260 <= word[0] < 292
    )
    team_rows = sorted(
        {word[1] for word in words if name_y + 5 <= word[1] <= name_y + 16 and 88 <= word[0] < 290}
    )
    team_y = team_rows[0] if team_rows else None
    team = (
        " ".join(
            word[4]
            for word in sorted(words, key=lambda value: value[0])
            if abs(word[1] - team_y) < 0.2 and 88 <= word[0] < 290
        )
        if team_y is not None
        else ""
    )
    return {
        "rider_number": int(number_words[0][4]),
        "rider": name,
        "team": team,
        "constructor": constructor,
        "nationality": nationality,
        "position": int(POSITION_RE.fullmatch(position_word[4]).group(1)),
        "declared_runs": None,
        "declared_total_laps": None,
        "declared_full_laps": None,
        "declared_valid_laps": None,
    }


def _is_run_header(row: list[Word]) -> bool:
    texts = {word[4] for word in row}
    return (
        "Run" in texts
        and "#" in texts
        and any(word[4].isdigit() and 60 <= _center(word) <= 85 for word in row)
    )


def _parse_run(
    row: list[Word],
    all_words: list[Word],
    y: float,
    rider: dict[str, Any],
    page: int,
    column: str,
) -> tuple[int, dict[str, Any]]:
    run = int(next(word[4] for word in row if word[4].isdigit() and 60 <= _center(word) <= 85))
    front = next(
        (word[4] for word in row if TYRE_RE.match(word[4]) and _center(word) < 200),
        None,
    )
    rear = next(
        (word[4] for word in row if TYRE_RE.match(word[4]) and _center(word) >= 200),
        None,
    )
    state_ys = sorted({word[1] for word in all_words if y + 0.5 < word[1] <= y + 13})
    state_y = state_ys[0] if state_ys else None
    state_words = (
        [word for word in all_words if abs(word[1] - state_y) < 0.2] if state_y is not None else []
    )
    front_new, front_age = _tyre_state(
        [word[4] for word in state_words if 125 <= _center(word) < 190]
    )
    rear_new, rear_age = _tyre_state(
        [word[4] for word in state_words if 225 <= _center(word) < 292]
    )
    record = {
        "year": rider["year"],
        "event": rider["event"],
        "session": rider["session"],
        "rider_number": rider["rider_number"],
        "rider": rider["rider"],
        "run": run,
        "front_tyre": front,
        "rear_tyre": rear,
        "front_tyre_new": front_new,
        "rear_tyre_new": rear_new,
        "front_tyre_laps_at_start": front_age,
        "rear_tyre_laps_at_start": rear_age,
        "source_page": page,
        "source_column": column,
    }
    return run, record


def _tyre_state(words: list[str]) -> tuple[bool | None, int | None]:
    if "New" in words:
        return True, 0
    age = next((int(word) for word in words if word.isdigit()), None)
    return (False, age) if age is not None else (None, None)


def _parse_lap_row(
    row: list[Word],
    rider: dict[str, Any],
    run: int,
    page: int,
    column: str,
    y: float,
) -> dict[str, Any] | None:
    lap_word = next((word for word in row if word[4].isdigit() and 25 <= _center(word) < 50), None)
    lap_time_word = _time_word(row, 48, 93)
    if not lap_word or not lap_time_word:
        return None
    markers = _cancellation_markers(row)
    record = {
        key: rider.get(key)
        for key in (
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
        )
    }
    record.update(
        {
            "run": run,
            "lap": int(lap_word[4]),
            "lap_time_seconds": parse_time(lap_time_word[4]),
            "t1": _cell_seconds(row, 103, 143),
            "t2": _cell_seconds(row, 143, 183),
            "t3": _cell_seconds(row, 183, 221),
            "t4": _cell_seconds(row, 221, 260),
            "speed": _speed(row),
            "pit_crossing": any(word[4] == "P" and 90 <= _center(word) < 105 for word in row),
            **markers,
            "source_page": page,
            "source_column": column,
            "source_y": y,
        }
    )
    return record


def _parse_partial_row(
    row: list[Word],
    rider: dict[str, Any],
    run: int,
    page: int,
    column: str,
    y: float,
) -> dict[str, Any] | None:
    row_kind = next((word[4] for word in row if word[4] in {"PIT", "unfinished"}), None)
    if not row_kind:
        return None
    markers = _cancellation_markers(row)
    return {
        "year": rider["year"],
        "event": rider["event"],
        "session": rider["session"],
        "rider_number": rider["rider_number"],
        "rider": rider["rider"],
        "run": run,
        "row_kind": row_kind,
        "t1": _cell_seconds(row, 103, 143),
        "t2": _cell_seconds(row, 143, 183),
        "t3": _cell_seconds(row, 183, 221),
        "t4": _cell_seconds(row, 221, 260),
        "speed": _speed(row),
        "pit_crossing": any(word[4] == "P" for word in row),
        "t1_cancelled": markers["t1_cancelled"],
        "t2_cancelled": markers["t2_cancelled"],
        "t3_cancelled": markers["t3_cancelled"],
        "t4_cancelled": markers["t4_cancelled"],
        "source_page": page,
        "source_column": column,
        "source_y": y,
    }


def _time_word(row: list[Word], low: float, high: float) -> Word | None:
    return next(
        (word for word in row if low <= _center(word) < high and TIME_RE.fullmatch(word[4])),
        None,
    )


def _cell_seconds(row: list[Word], low: float, high: float) -> float | None:
    word = _time_word(row, low, high)
    return parse_time(word[4]) if word else None


def _speed(row: list[Word]) -> float | None:
    word = next(
        (word for word in row if 260 <= _center(word) < 292 and re.fullmatch(r"\d+\.\d", word[4])),
        None,
    )
    return float(word[4]) if word else None


def _cancellation_markers(row: list[Word]) -> dict[str, bool]:
    result = {
        "lap_cancelled": False,
        "t1_cancelled": False,
        "t2_cancelled": False,
        "t3_cancelled": False,
        "t4_cancelled": False,
    }
    for word in row:
        if word[4] != "*":
            continue
        center = _center(word)
        key = (
            "lap_cancelled"
            if center < 115
            else "t1_cancelled"
            if center < 150
            else "t2_cancelled"
            if center < 190
            else "t3_cancelled"
            if center < 230
            else "t4_cancelled"
        )
        result[key] = True
    return result


def _validate_and_classify(
    laps: pd.DataFrame, session: str, sector_tolerance_seconds: float
) -> pd.DataFrame:
    laps = LAP_SCHEMA.validate(laps, lazy=True)
    boolean_columns = [
        "pit_crossing",
        "lap_cancelled",
        "t1_cancelled",
        "t2_cancelled",
        "t3_cancelled",
        "t4_cancelled",
    ]
    laps[boolean_columns] = laps[boolean_columns].fillna(False).astype(bool)
    sectors = ["t1", "t2", "t3", "t4"]
    laps["first_in_run"] = laps["lap"].eq(
        laps.groupby(["rider_number", "run"])["lap"].transform("min")
    )
    laps["timing_complete"] = laps[sectors].notna().all(axis=1)
    laps["speed_available"] = laps["speed"].notna()
    laps["sector_sum_delta"] = laps[sectors].sum(axis=1, min_count=4) - laps["lap_time_seconds"]
    sector_ok = pd.Series(pd.NA, index=laps.index, dtype="boolean")
    available = laps["sector_sum_delta"].notna()
    sector_ok.loc[available] = (
        laps.loc[available, "sector_sum_delta"].abs().le(sector_tolerance_seconds)
    )
    laps["sector_sum_ok"] = sector_ok
    laps["is_full_lap"] = laps["timing_complete"] & ~laps["first_in_run"] & ~laps["pit_crossing"]
    cancelled = laps[
        [
            "lap_cancelled",
            "t1_cancelled",
            "t2_cancelled",
            "t3_cancelled",
            "t4_cancelled",
        ]
    ].any(axis=1)
    laps["official_valid"] = laps["is_full_lap"] & ~cancelled

    laps["classification"] = "CLEAN"
    invalid = ~laps["official_valid"] | ~laps["sector_sum_ok"].fillna(False).astype(bool)
    laps.loc[invalid, "classification"] = "INVALID"
    if session in {"SPR", "RAC"}:
        opening_lap = laps["lap"].eq(1)
        laps.loc[laps["first_in_run"] & ~opening_lap, "classification"] = "OUTLAP"
        laps.loc[opening_lap, "classification"] = "OPENING_LAP"
    else:
        laps.loc[laps["first_in_run"], "classification"] = "OUTLAP"
    laps.loc[laps["pit_crossing"], "classification"] = "PIT_IN"

    clean_groups = laps[laps["classification"] == "CLEAN"].groupby("rider_number").groups
    for _, indices in clean_groups.items():
        times = laps.loc[indices, "lap_time_seconds"]
        if len(times) < 5:
            continue
        q1, q3 = times.quantile([0.25, 0.75])
        laps.loc[indices[times > q3 + 3 * (q3 - q1)], "classification"] = "SLOW"

    laps["is_fastest"] = False
    valid = laps[laps["official_valid"]]
    if not valid.empty:
        fastest = valid.groupby("rider_number")["lap_time_seconds"].transform("min")
        laps.loc[valid.index, "is_fastest"] = valid["lap_time_seconds"].eq(fastest)
    return laps.sort_values(["position", "lap"]).reset_index(drop=True)


def _quality_report(
    laps: pd.DataFrame,
    runs: pd.DataFrame,
    partials: pd.DataFrame,
    riders: dict[int, dict[str, Any]],
    sector_tolerance_seconds: float,
) -> dict[str, Any]:
    warnings: list[str] = []
    reconciliation: list[dict[str, Any]] = []
    for number, rider in riders.items():
        rider_laps = laps[laps["rider_number"] == number]
        rider_runs = runs[runs["rider_number"] == number]
        actual = {
            "rider_number": number,
            "rider": rider["rider"],
            "runs": len(rider_runs),
            "laps": len(rider_laps),
            "full_laps": int(rider_laps["is_full_lap"].sum()),
            "valid_laps": int(rider_laps["official_valid"].sum()),
        }
        expected = {
            "runs": rider.get("declared_runs"),
            "laps": rider.get("declared_total_laps"),
            "full_laps": rider.get("declared_full_laps"),
            "valid_laps": rider.get("declared_valid_laps"),
        }
        mismatches = [key for key, value in expected.items() if value != actual[key]]
        if mismatches:
            warnings.append(f"{rider['rider']} reconciliation mismatch: {', '.join(mismatches)}")
        reconciliation.append({**actual, "expected": expected, "mismatches": mismatches})

    sectors = ["t1", "t2", "t3", "t4"]
    full_sector_failures = laps["is_full_lap"] & ~laps["sector_sum_ok"].fillna(False).astype(bool)
    if full_sector_failures.any():
        warnings.append(f"{int(full_sector_failures.sum())} full laps fail the sector-sum check")
    missing_tyre_runs = int(runs[["front_tyre", "rear_tyre"]].isna().any(axis=1).sum())
    if missing_tyre_runs:
        warnings.append(f"{missing_tyre_runs} runs have missing tyre compounds")
    return {
        "riders_detected": len(riders),
        "runs_detected": len(runs),
        "laps_detected": len(laps),
        "valid_laps": int(laps["official_valid"].sum()),
        "partial_rows": len(partials),
        "sector_completeness": round(
            float(laps[sectors].notna().sum().sum() / (len(laps) * len(sectors))), 6
        ),
        "missing_values": {
            column: int(laps[column].isna().sum())
            for column in ["lap_time_seconds", *sectors, "speed"]
        },
        "sector_tolerance_seconds": sector_tolerance_seconds,
        "sector_sum_failures": int(full_sector_failures.sum()),
        "reconciliation": reconciliation,
        "parser_warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
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
