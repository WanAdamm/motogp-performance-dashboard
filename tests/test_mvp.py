from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import fitz
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from motogp_analytics import (
    analysis_url,
    discover_sessions,
    format_time,
    load_laps,
    matched_lap_deltas,
    parse_pdf,
    parse_time,
    rider_summary,
    select_full_session_riders,
    select_scope,
)
from motogp_analytics._parsing import _parse_rider_header, _rows
from motogp_analytics.core import detect_session, save_session

ROOT = Path(__file__).parents[1]
SAMPLES = ROOT / "SPA 2025"


def sample(name: str) -> Path:
    path = SAMPLES / name
    if not path.exists():
        pytest.skip("Local MotoGP sample PDFs are not available")
    return path


def make_synthetic_sprint(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=595, height=842)

    def add(x: float, y: float, text: str, size: float = 8) -> None:
        page.insert_text((x, y), text, fontsize=size)

    add(30, 70, "GRAND PRIX OF SPAIN", 12)
    add(30, 86, "TISSOT SPRINT", 12)
    add(30, 102, "2025", 9)
    add(36, 220, "1st", 12)
    add(68, 220, "93", 12)
    add(91, 220, "Marc MARQUEZ", 10)
    add(206, 220, "DUCATI", 9)
    add(273, 220, "SPA", 9)
    add(91, 232, "Ducati Lenovo Team", 8)
    add(91, 245, "Runs=2 Total laps=6 Full laps=4 Valid laps=4", 8)

    def add_run(y: float, run: int, laps: list[tuple[int, float]], missing_speed: int = 0) -> None:
        add(38, y, "Run")
        add(60, y, "#")
        add(71, y, str(run))
        add(93, y, "Front Tyre")
        add(134, y, "Wet-Medium")
        add(193, y, "Rear Tyre")
        add(230, y, "Wet-Soft")
        add(146, y + 11, "New Tyre")
        add(243, y + 11, "New Tyre")
        for offset, (lap, lap_time) in enumerate(laps, start=1):
            row_y = y + 25 + offset * 12
            sectors = [24.0, 14.0, lap_time - 68.0, 30.0]
            add(40, row_y, str(lap))
            add(59, row_y, f"1'{lap_time - 60:06.3f}")
            for x, value in zip((111, 151, 187, 227), sectors, strict=True):
                add(x, row_y, f"{value:.3f}")
            if lap != missing_speed:
                add(264, row_y, "295.0")

    add_run(258, 1, [(1, 100.0), (2, 98.0), (3, 97.9)])
    add_run(332, 2, [(4, 98.1), (5, 98.2), (6, 98.3)], missing_speed=6)

    add(36, 430, "2nd", 12)
    add(68, 430, "73", 12)
    add(91, 430, "Alex MARQUEZ", 10)
    add(206, 430, "DUCATI", 9)
    add(273, 430, "SPA", 9)
    add(91, 442, "BK8 Gresini Racing MotoGP", 8)
    add(91, 455, "Runs=2 Total laps=5 Full laps=3 Valid laps=3", 8)
    add_run(468, 1, [(1, 100.5), (2, 98.5), (3, 98.4)])
    add_run(542, 2, [(4, 98.6), (5, 98.7)])

    document.save(path)
    document.close()
    return path


@pytest.fixture(scope="module")
def race():
    return parse_pdf(sample("SPA 2025 RAC.pdf"), year=2025, event="SPA", session="RAC")


@pytest.fixture(scope="module")
def practice():
    return parse_pdf(sample("SPA 2025 PR.pdf"), year=2025, event="SPA", session="PR")


@pytest.fixture(scope="module")
def sprint():
    return parse_pdf(sample("SPA 2025 SPR.pdf"), year=2025, event="SPA", session="SPR")


@pytest.fixture(scope="module")
def synthetic_session(tmp_path_factory):
    path = make_synthetic_sprint(tmp_path_factory.mktemp("synthetic") / "Analysis.pdf")
    return parse_pdf(path, year=2025, event="SPA", session="SPR")


def test_time_conversion_and_url() -> None:
    assert parse_time("1'37.706") == pytest.approx(97.706)
    assert parse_time("50'43.702") == pytest.approx(3043.702)
    assert analysis_url(2025, "spa", "SPR").endswith("/2025/SPA/MotoGP/SPR/Analysis.pdf")
    assert format_time(-1.234) == "-1.234"
    assert format_time(-0.00001) == "0.000"
    with pytest.raises(ValueError, match="Invalid event code"):
        analysis_url(2025, "../outside", "SPR")


def test_detect_session_accepts_standalone_grand_prix() -> None:
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((30, 70), "GRAND PRIX OF HUNGARY")
        page.insert_text((30, 90), "GRAND PRIX")
        assert detect_session(document) == "RAC"


def test_coordinate_helpers_allow_minor_font_box_offsets() -> None:
    row = [
        (35.0, 100.61, 45.0, 108.0, "2"),
        (55.0, 100.0, 90.0, 108.0, "1'40.273"),
        (110.0, 100.61, 135.0, 108.0, "29.771"),
    ]
    assert list(_rows(row).values()) == [row]

    position = (36.0, 10.0, 55.0, 12.0, "1st")
    header = _parse_rider_header(
        [
            position,
            (68.0, 10.0, 82.0, 12.0, "93"),
            (91.0, 8.0, 155.0, 10.0, "Marc MARQUEZ"),
            (205.0, 8.38, 250.0, 10.0, "DUCATI"),
            (270.0, 8.38, 288.0, 10.0, "SPA"),
            (91.0, 18.0, 190.0, 20.0, "Ducati Lenovo Team"),
        ],
        position,
    )
    assert (header["constructor"], header["nationality"]) == ("DUCATI", "SPA")


def test_matched_lap_deltas_use_shared_laps_and_a_minus_b() -> None:
    laps = pd.DataFrame(
        {
            "rider": ["A", "A", "B", "B"],
            "lap": [1, 2, 2, 3],
            "lap_time_seconds": [100.0, 99.1, 99.4, 99.0],
        }
    )
    comparison = matched_lap_deltas(laps, "A", "B")
    assert comparison[["lap", "delta"]].to_dict("records") == [{"lap": 2, "delta": -0.3}]


def test_full_session_filter_keeps_only_riders_with_every_lap() -> None:
    laps = pd.DataFrame(
        {
            "rider_number": [1, 1, 1, 2, 2, 3, 3],
            "lap": [1, 2, 3, 1, 2, 1, 3],
        }
    )

    filtered = select_full_session_riders(laps)

    assert filtered["rider_number"].unique().tolist() == [1]
    assert filtered["lap"].tolist() == [1, 2, 3]


def test_consistency_score_normalizes_eligible_rider_iqrs() -> None:
    rows = []
    for rider_number, rider, times in [
        (1, "A", [100.0, 101.0, 102.0]),
        (2, "B", [100.0, 102.0, 104.0]),
        (3, "C", [100.0, 103.0, 106.0]),
        (4, "D", [100.0, 110.0]),
    ]:
        for lap_time in times:
            rows.append(
                {
                    "rider_number": rider_number,
                    "rider": rider,
                    "team": rider,
                    "constructor": rider,
                    "lap_time_seconds": lap_time,
                    "official_valid": True,
                    "sector_sum_ok": True,
                    "classification": "CLEAN",
                    "speed": 300.0,
                    "t1": 25.0,
                    "t2": 25.0,
                    "t3": 25.0,
                    "t4": 25.0,
                }
            )

    laps = pd.DataFrame(rows)
    summary = rider_summary(laps)
    scores = summary.set_index("rider")["consistency_score"]

    assert summary.columns.get_loc("consistency_score") == summary.columns.get_loc("iqr") + 1
    assert scores.loc[["A", "B", "C"]].tolist() == pytest.approx([100.0, 50.0, 0.0])
    assert pd.isna(scores["D"])

    single_eligible = rider_summary(laps[laps["rider"].isin(["A", "D"])]).set_index("rider")
    assert single_eligible.loc["A", "consistency_score"] == 100.0


def test_synthetic_pipeline_is_self_contained(tmp_path: Path, synthetic_session) -> None:
    parsed = synthetic_session
    assert (len(parsed.laps), len(parsed.runs), len(parsed.partials)) == (11, 4, 0)
    assert parsed.quality["parser_warnings"] == []
    assert set(parsed.runs["front_tyre"]) == {"Wet-Medium"}
    assert parsed.laps.query("lap == 1").iloc[0]["classification"] == "OPENING_LAP"
    assert parsed.laps.query("lap == 4").iloc[0]["classification"] == "OUTLAP"
    lap_six = parsed.laps.query("lap == 6").iloc[0]
    assert lap_six["official_valid"]
    assert not lap_six["speed_available"]

    destination = save_session(parsed, tmp_path)
    save_session(parsed, tmp_path)
    assert len(load_laps(destination)) == 11
    assert discover_sessions(tmp_path) == [destination]
    assert not list(destination.parent.glob(".session=SPR.backup-*"))
    assert rider_summary(load_laps(destination)).iloc[0]["rider"] == "Marc MARQUEZ"

    invalid_only = parsed.laps.copy()
    invalid_only["classification"] = "INVALID"
    assert rider_summary(invalid_only).empty


def test_pdf_identity_validation(synthetic_session) -> None:
    path = synthetic_session.source_path
    with pytest.raises(ValueError, match="Year mismatch"):
        parse_pdf(path, year=2024, event="SPA", session="SPR")
    with pytest.raises(ValueError, match="Event mismatch"):
        parse_pdf(path, year=2025, event="FRA", session="SPR")


def test_race_parser_reconciles_and_keeps_coordinate_cells(race) -> None:
    assert (len(race.laps), len(race.runs), len(race.partials)) == (521, 23, 5)
    assert race.quality["parser_warnings"] == []
    assert "Maverick VIÑALES" in set(race.laps["rider"])

    alex_lap_five = race.laps.query("rider_number == 73 and lap == 5").iloc[0]
    assert alex_lap_five["t3"] == pytest.approx(29.065)
    assert alex_lap_five["t4"] == pytest.approx(29.790)
    assert alex_lap_five["speed"] == pytest.approx(293.4)

    enea_lap_eight = race.laps.query("rider_number == 23 and lap == 8").iloc[0]
    assert enea_lap_eight["lap_cancelled"]
    assert enea_lap_eight["t2_cancelled"]
    assert enea_lap_eight["t3"] == pytest.approx(29.697)

    pit = race.partials.query("rider_number == 54 and row_kind == 'PIT'").iloc[0]
    assert pit[["t1", "t2", "t3", "t4", "speed"]].tolist() == pytest.approx(
        [24.514, 14.321, 29.481, 29.733, 291.1]
    )


def test_practice_parser_preserves_runs_and_sparse_rows(practice) -> None:
    assert (len(practice.laps), len(practice.runs), len(practice.partials)) == (538, 119, 3)
    assert practice.quality["parser_warnings"] == []

    run = practice.runs.query("rider_number == 73 and run == 3").iloc[0]
    assert run["front_tyre"] == "Slick-Medium"
    assert run["rear_tyre"] == "Slick-Soft"
    assert run["front_tyre_laps_at_start"] == 4
    assert run["rear_tyre_new"]

    sparse = practice.laps.query("rider_number == 73 and lap == 5").iloc[0]
    assert sparse["lap_time_seconds"] == pytest.approx(3043.702)
    assert sparse["pit_crossing"]
    assert sparse[["t2", "t3", "t4", "speed"]].isna().all()
    clean_theory = rider_summary(practice.laps, scope="clean").set_index("rider_number")
    raw_theory = rider_summary(practice.laps, scope="raw").set_index("rider_number")
    assert raw_theory.loc[73, "theoretical_best"] == clean_theory.loc[73, "theoretical_best"]


def test_session_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="expected FP1, PDF contains RAC"):
        parse_pdf(sample("SPA 2025 FP1.pdf"), year=2025, event="SPA", session="FP1")


def test_parquet_duckdb_and_analytics_round_trip(tmp_path: Path, sprint) -> None:
    destination = save_session(sprint, tmp_path)
    assert {path.name for path in destination.iterdir()} == {
        "laps.parquet",
        "runs.parquet",
        "partials.parquet",
        "session.json",
    }
    metadata = json.loads((destination / "session.json").read_text(encoding="utf-8"))
    assert metadata["quality"]["parser_warnings"] == []

    laps = load_laps(destination)
    assert len(laps) == 250
    assert len(select_scope(laps, "raw")) > len(select_scope(laps, "clean"))
    summary = rider_summary(laps)
    assert summary.iloc[0]["rider"] == "Marc MARQUEZ"
    assert summary.iloc[0]["potential_lost"] == pytest.approx(0.161)


def test_streamlit_dashboard_smoke(tmp_path: Path, synthetic_session, monkeypatch) -> None:
    save_session(synthetic_session, tmp_path)
    monkeypatch.setenv("MOTOGP_DATA_ROOT", str(tmp_path))
    app = AppTest.from_file(ROOT / "dashboard" / "app.py").run(timeout=30)
    assert not app.exception
    assert len(app.tabs) == 4
    assert app.toggle("exclude_incomplete_riders").label == "Exclude incomplete riders"
    assert not app.toggle("exclude_incomplete_riders").value
    assert app.toggle("race_time_format").label == "Use race time format"
    assert not app.toggle("race_time_format").value

    comparison = next(
        frame.value for frame in app.dataframe if "fastest (seconds)" in frame.value.index
    )
    assert comparison.index.tolist() == [
        "laps (count)",
        "fastest (seconds)",
        "median (seconds)",
        "iqr (seconds)",
        "consistency_score (0-100)",
        "theoretical_best (seconds)",
        "potential_lost (seconds)",
        "top_speed (km/h)",
    ]
    assert comparison.loc["fastest (seconds)", "Marc MARQUEZ"] == "97.900"

    app = app.toggle("race_time_format").set_value(True).run(timeout=30)
    assert not app.exception
    race_comparison = next(
        frame.value for frame in app.dataframe if "fastest (race format)" in frame.value.index
    )
    assert "iqr (race format)" in race_comparison.index
    assert race_comparison.loc["fastest (race format)", "Marc MARQUEZ"] == "1'37.900"

    app = app.toggle("exclude_incomplete_riders").set_value(True).run(timeout=30)
    assert not app.exception
    assert app.multiselect[0].options == ["Marc MARQUEZ"]
    assert any("requires two riders" in info.value for info in app.info)


def test_dashboard_separates_event_and_session_navigation(
    tmp_path: Path, synthetic_session, monkeypatch
) -> None:
    def variant(event: str, session: str, lap_offset: float = 0.0):
        laps = synthetic_session.laps.assign(event=event, session=session).copy()
        laps["lap_time_seconds"] += lap_offset
        return replace(
            synthetic_session,
            event=event,
            session=session,
            observed_session=session,
            laps=laps,
            runs=synthetic_session.runs.assign(event=event, session=session),
            partials=synthetic_session.partials.assign(event=event, session=session),
        )

    save_session(variant("SPA", "SPR"), tmp_path)
    save_session(variant("SPA", "RAC", 10.0), tmp_path)
    save_session(variant("ARA", "FP1", 20.0), tmp_path)
    save_session(variant("ARA", "RAC", 20.0), tmp_path)
    save_session(variant("NED", "RAC", 30.0), tmp_path)
    monkeypatch.setenv("MOTOGP_DATA_ROOT", str(tmp_path))

    app = AppTest.from_file(ROOT / "dashboard" / "app.py")
    app.query_params = {"event": "2025-spa", "session": "SPR"}
    app.run(timeout=30)

    event_selector = app.selectbox("selected_event")
    assert set(event_selector.options) == {
        "2025 Netherlands",
        "2025 Spain - Jerez",
        "2025 Spain - MotorLand Aragon",
    }
    assert event_selector.value == "2025-spa"
    session_selector = app.segmented_control("selected_session")
    assert session_selector.options == ["Sprint", "Race"]
    assert session_selector.value == "SPR"
    assert app.query_params == {"event": ["2025-spa"], "session": ["SPR"]}
    assert not any("sector-ribbon" in item.value for item in app.markdown)
    assert any("1&#x27;37.900" in item.value for item in app.markdown)

    app = session_selector.set_value(None).run(timeout=30)
    assert not app.exception
    assert app.segmented_control("selected_session").value == "SPR"
    assert app.query_params == {"event": ["2025-spa"], "session": ["SPR"]}

    app.query_params = {"event": "2025-ara", "session": "FP1"}
    app.run(timeout=30)
    assert not app.exception
    assert app.selectbox("selected_event").value == "2025-ara"
    assert app.segmented_control("selected_session").value == "FP1"
    assert app.query_params == {"event": ["2025-ara"], "session": ["FP1"]}
    assert any("1&#x27;57.900" in item.value for item in app.markdown)

    app = app.selectbox("selected_event").set_value("2025-spa").run(timeout=30)
    assert app.segmented_control("selected_session").value == "RAC"
    assert any("1&#x27;47.900" in item.value for item in app.markdown)
    app = app.segmented_control("selected_session").set_value("SPR").run(timeout=30)
    assert not app.exception
    assert app.query_params == {"event": ["2025-spa"], "session": ["SPR"]}
    assert any("1&#x27;37.900" in item.value for item in app.markdown)
