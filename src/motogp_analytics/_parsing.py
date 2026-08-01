"""Coordinate-aware extraction of timing records from MotoGP analysis PDFs."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import fitz
import pandas as pd

from ._classification import _quality_report, _validate_and_classify
from ._contracts import (
    LAP_COLUMNS,
    PARTIAL_COLUMNS,
    RUN_COLUMNS,
    SECTOR_TOLERANCE_SECONDS,
    ParsedSession,
    _event_code,
    _session_code,
)

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
TYRE_RE = re.compile(r"^(?:Slick|Wet)-")
EVENT_TITLE_MARKERS = {
    "SPA": "GRAND PRIX OF SPAIN",
    "FRA": "GRAND PRIX DE FRANCE",
    "HUN": "GRAND PRIX OF HUNGARY",
}
COLUMN_SPLIT = 297.5
RIGHT_OFFSET = 272.2
ROW_Y_TOLERANCE = 1.0

Word = tuple[float, float, float, float, str]


def parse_time(value: str) -> float:
    """Parse a PDF timing cell into numeric seconds."""

    if not TIME_RE.fullmatch(value):
        raise ValueError(f"Invalid timing value: {value!r}")
    if "'" not in value:
        return float(value)
    minutes, seconds = value.split("'", 1)
    return int(minutes) * 60 + float(seconds)


def detect_session(document: fitz.Document) -> str:
    """Identify the official session code from the first-page title."""

    text = document[0].get_text().upper()
    for title, code in SESSION_TITLES:
        if title in text:
            return code
    # New race templates use this standalone label, while event titles contain it as a phrase.
    if "GRAND PRIX" in {line.strip() for line in text.splitlines()}:
        return "RAC"
    raise ValueError("Could not identify session from PDF title")


def parse_pdf(
    pdf_path: str | Path,
    *,
    year: int,
    event: str,
    session: str,
    sector_tolerance_seconds: float = SECTOR_TOLERANCE_SECONDS,
) -> ParsedSession:
    """Parse, validate, and classify one two-column timing analysis PDF."""

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

    # Rider and run state intentionally spans columns and pages because blocks can continue.
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
        if current_y is None or abs(word[1] - current_y) > ROW_Y_TOLERANCE:
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
        if abs(word[1] - name_y) <= 0.5 and 202 <= word[0] < 260
    )
    nationality = " ".join(
        word[4]
        for word in sorted(words, key=lambda value: value[0])
        if abs(word[1] - name_y) <= 0.5 and 260 <= word[0] < 292
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
