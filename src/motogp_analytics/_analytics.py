"""Lap-scope selection and rider-level pace analytics."""

from __future__ import annotations

from typing import Any

import pandas as pd

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
    "consistency_score",
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


def rider_summary(laps: pd.DataFrame, *, scope: str = "clean") -> pd.DataFrame:
    """Summarize rider pace while keeping sector eligibility independent of pace scope."""

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
    summary = (
        pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
        .sort_values("median", na_position="last")
        .reset_index(drop=True)
    )
    eligible = summary["laps"] >= 3
    eligible_iqrs = summary.loc[eligible, "iqr"]
    if not eligible_iqrs.empty:
        iqr_span = eligible_iqrs.max() - eligible_iqrs.min()
        summary.loc[eligible, "consistency_score"] = (
            100.0
            if iqr_span == 0
            else (100 * (eligible_iqrs.max() - eligible_iqrs) / iqr_span).round(1)
        )
    return summary


def select_scope(laps: pd.DataFrame, scope: str) -> pd.DataFrame:
    """Select clean analysis laps or all rows with an observed lap time."""

    if scope == "clean":
        return laps[laps["classification"] == "CLEAN"].copy()
    if scope == "raw":
        return laps[laps["lap_time_seconds"].notna()].copy()
    raise ValueError("Scope must be 'clean' or 'raw'")


def format_time(seconds: float | None) -> str:
    """Format numeric seconds using standard motorsport timing notation."""

    if seconds is None or pd.isna(seconds):
        return "—"
    value = round(float(seconds), 3)
    sign = "-" if value < 0 else ""
    minutes, remainder = divmod(abs(value), 60)
    formatted = f"{int(minutes)}'{remainder:06.3f}" if minutes else f"{remainder:.3f}"
    return f"{sign}{formatted}"


def pace_leaders(summary: pd.DataFrame) -> dict[str, pd.Series | None]:
    """Select the dashboard pace leaders from a non-empty rider summary."""

    consistent = summary[summary["laps"] >= 3]
    speed = summary.dropna(subset=["top_speed"])
    return {
        "fastest": summary.loc[summary["fastest"].idxmin()],
        "best_median": summary.loc[summary["median"].idxmin()],
        "most_consistent": consistent.loc[consistent["iqr"].idxmin()]
        if not consistent.empty
        else None,
        "top_speed": speed.loc[speed["top_speed"].idxmax()] if not speed.empty else None,
    }


def sector_deficits(summary: pd.DataFrame) -> pd.DataFrame:
    """Return each rider's median-sector deficit to the session benchmark."""

    columns = ["median_t1", "median_t2", "median_t3", "median_t4"]
    values = summary.set_index("rider")[columns]
    return values - values.min(axis=0)


def matched_lap_deltas(laps: pd.DataFrame, rider_a: str, rider_b: str) -> pd.DataFrame:
    """Compare matching lap numbers as rider A time minus rider B time."""

    a_laps = laps[laps["rider"] == rider_a][["lap", "lap_time_seconds"]]
    b_laps = laps[laps["rider"] == rider_b][["lap", "lap_time_seconds"]]
    comparison = a_laps.merge(b_laps, on="lap", suffixes=("_a", "_b"))
    comparison["delta"] = (
        comparison["lap_time_seconds_a"] - comparison["lap_time_seconds_b"]
    ).round(3)
    return comparison
