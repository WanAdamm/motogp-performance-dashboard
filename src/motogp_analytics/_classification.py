"""Lap validation, derived classification, and session quality reporting."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pandera.pandas as pa

from ._contracts import SUPPORTED_SESSIONS

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


def _validate_and_classify(
    laps: pd.DataFrame, session: str, sector_tolerance_seconds: float
) -> pd.DataFrame:
    """Validate parsed laps and derive analysis classifications without altering raw status."""

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
    """Reconcile parsed records with declared counts and report data completeness."""

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
