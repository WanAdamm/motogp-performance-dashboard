from __future__ import annotations

import html
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.styles import DASHBOARD_CSS, chart_colors, chart_layout, get_theme, theme_css
from motogp_analytics import (
    discover_sessions,
    format_time,
    load_laps,
    load_session_metadata,
    matched_lap_deltas,
    pace_leaders,
    rider_summary,
    sector_deficits,
    select_scope,
)

st.set_page_config(
    page_title="MotoGP Pace Lab",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="auto",
)

THEME_NAME = st.context.theme.type or "light"
THEME = get_theme(THEME_NAME)
st.markdown(theme_css(THEME), unsafe_allow_html=True)
st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

DATA_ROOT = Path(os.environ.get("MOTOGP_DATA_ROOT", "data"))
CONSTRUCTOR_COLORS, TRACE_COLORS, SECTOR_COLORS = chart_colors(THEME_NAME, THEME)


@st.cache_data(show_spinner=False)
def read_laps(path: str, modified: float) -> pd.DataFrame:
    del modified
    return load_laps(path)


def session_values(path: Path) -> dict[str, str]:
    return {part.split("=", 1)[0]: part.split("=", 1)[1] for part in path.parts if "=" in part}


def session_label(path: Path) -> str:
    values = session_values(path)
    return f"{values['year']}  /  {values['event']}  /  {values['session']}"


def timing_card(label: str, value: str, detail: str, tone: str = "") -> None:
    st.markdown(
        f"""
        <div class="timing-card {tone}">
            <div class="label">{html.escape(label)}</div>
            <div class="value">{html.escape(value)}</div>
            <div class="detail">{html.escape(detail)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_number(value: float | None, decimals: int) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.{decimals}f}"


sessions = discover_sessions(DATA_ROOT)
if not sessions:
    st.markdown(
        """
        <div class="hero hero-empty">
            <div class="hero-kicker">No timing feed</div>
            <h1><span>No session.</span><strong>No signal.</strong></h1>
            <p>Run the local PDF through the validated coordinate parser, then reload this page.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.code("uv run motogp-analytics ingest --year 2025 --event SPA --session SPR")
    st.stop()

with st.sidebar:
    st.markdown('<div class="data-label">Timing feed</div>', unsafe_allow_html=True)
    selected_path = st.selectbox("Session", sessions, format_func=session_label)
    scope = st.radio("Pace view", ["clean", "raw"], horizontal=True)
    st.caption(
        "Clean excludes opening, out, pit, cancelled, incomplete, and anomalously slow laps."
    )
    st.caption("Sector potential always uses complete, officially valid timing observations.")

metadata = load_session_metadata(selected_path)
laps_path = selected_path / "laps.parquet"
laps = read_laps(str(selected_path), laps_path.stat().st_mtime)
summary = rider_summary(laps, scope=scope)
selected_laps = select_scope(laps, scope)
session = session_values(selected_path)

st.markdown(
    f"""
    <div class="hero">
        <div class="session-stamp">
            <div class="stamp-event">{html.escape(session["event"])} · MotoGP</div>
            <div class="stamp-session">{html.escape(session["session"])}</div>
            <div class="stamp-year">{html.escape(session["year"])}</div>
        </div>
        <div class="hero-copy">
            <div class="hero-kicker">Performance analysis · {html.escape(scope)} pace</div>
            <h1><span>The result shows where.</span><strong>Pace shows why.</strong></h1>
            <p>Compare repeatable lap speed, sector contribution, and execution potential from
            the official timing analysis.</p>
        </div>
        <svg class="hero-trace" viewBox="0 0 640 200" aria-hidden="true">
            <path d="M18 166 C122 30, 238 188, 344 76 S526 30, 622 112"
                  fill="none" stroke="{THEME["cobalt"]}" stroke-width="5" />
            <circle cx="622" cy="112" r="9" fill="{THEME["kerb_red"]}" />
        </svg>
    </div>
    <div class="sector-ribbon">
        <span>SECTOR · T1</span><span>SECTOR · T2</span>
        <span>SECTOR · T3</span><span>SECTOR · T4</span>
    </div>
    """,
    unsafe_allow_html=True,
)

if summary.empty:
    st.warning(f"No {scope} laps are available for this session.")
    st.stop()

leaders = pace_leaders(summary)
fastest = leaders["fastest"]
best_median = leaders["best_median"]
most_consistent = leaders["most_consistent"]
top_speed = leaders["top_speed"]

cards = st.columns(4)
with cards[0]:
    timing_card("Fastest lap", format_time(fastest["fastest"]), fastest["rider"])
with cards[1]:
    timing_card("Best median", format_time(best_median["median"]), best_median["rider"], "caution")
with cards[2]:
    if most_consistent is None:
        timing_card("Tightest IQR", "Unavailable", "Requires at least three laps")
    else:
        timing_card(
            "Tightest IQR",
            f"{most_consistent['iqr']:.3f}s",
            most_consistent["rider"],
        )
with cards[3]:
    if top_speed is None:
        timing_card("Top speed", "Unavailable", "No speed-trap observations", "signal")
    else:
        timing_card(
            "Top speed",
            f"{top_speed['top_speed']:.1f} km/h",
            top_speed["rider"],
            "signal",
        )

pace_tab, sector_tab, compare_tab, quality_tab = st.tabs(
    ["Pace distribution", "Sector map", "Head-to-head", "Data quality"]
)

with pace_tab:
    pace = go.Figure()
    order = summary["rider"].tolist()
    for rider in order:
        rider_laps = selected_laps[selected_laps["rider"] == rider]
        constructor = rider_laps["constructor"].iloc[0]
        pace.add_trace(
            go.Box(
                x=rider_laps["lap_time_seconds"],
                y=[rider] * len(rider_laps),
                name=rider,
                orientation="h",
                marker_color=CONSTRUCTOR_COLORS.get(constructor, THEME["cobalt"]),
                boxpoints=False,
                hovertemplate=f"{rider}<br>%{{x:.3f}}s<extra></extra>",
            )
        )
    pace.update_layout(title="Repeatable pace window", showlegend=False)
    pace.update_yaxes(categoryorder="array", categoryarray=list(reversed(order)))
    pace.update_xaxes(title="Lap time (seconds)")
    st.plotly_chart(chart_layout(pace, THEME, height=max(520, len(order) * 29)), width="stretch")

    defaults = order[: min(5, len(order))]
    riders_to_plot = st.multiselect("Riders on trace", order, default=defaults)
    evolution_data = selected_laps[selected_laps["rider"].isin(riders_to_plot)].copy()
    evolution_data["trace"] = evolution_data["rider"] + " · R" + evolution_data["run"].astype(str)
    evolution = px.line(
        evolution_data,
        x="lap",
        y="lap_time_seconds",
        color="rider",
        line_group="trace",
        markers=True,
        color_discrete_sequence=TRACE_COLORS,
        title="Lap-time evolution",
        labels={"lap_time_seconds": "Lap time (seconds)", "lap": "Lap"},
    )
    st.plotly_chart(chart_layout(evolution, THEME), width="stretch")

with sector_tab:
    deltas = sector_deficits(summary)
    if deltas.dropna(how="all").empty:
        st.info("No complete, valid sector observations are available.")
    else:
        heatmap = go.Figure(
            go.Heatmap(
                z=deltas.to_numpy(),
                x=["T1", "T2", "T3", "T4"],
                y=deltas.index,
                colorscale=SECTOR_COLORS,
                colorbar=dict(title="Delta (s)"),
                texttemplate="+%{z:.3f}",
                textfont=dict(color=THEME["graphite"]),
                hovertemplate="%{y}<br>%{x}: +%{z:.3f}s<extra></extra>",
            )
        )
        heatmap.update_layout(title="Median sector deficit to benchmark")
        st.plotly_chart(
            chart_layout(heatmap, THEME, height=max(520, len(summary) * 29)), width="stretch"
        )

    theory = summary[
        ["rider", "theoretical_reference", "theoretical_best", "potential_lost"]
    ].copy()
    theory = theory.rename(columns={"theoretical_reference": "fastest"})
    for column in ["fastest", "theoretical_best", "potential_lost"]:
        theory[column] = theory[column].map(format_time)
    st.dataframe(
        theory.rename(
            columns={
                "rider": "Rider",
                "fastest": "Fastest",
                "theoretical_best": "Theoretical best",
                "potential_lost": "Potential lost",
            }
        ),
        hide_index=True,
        width="stretch",
    )

with compare_tab:
    comparison_riders = summary["rider"].tolist()
    if len(comparison_riders) < 2:
        st.info("Head-to-head requires two riders with laps in the selected pace view.")
    else:
        left, right = st.columns(2)
        rider_a = left.selectbox("Rider A", comparison_riders, index=0)
        rider_b = right.selectbox("Rider B", comparison_riders, index=1)
        race_time_format = st.toggle(
            "Use race time format",
            help="Off displays timing values in seconds.",
        )
        comparison = summary[summary["rider"].isin([rider_a, rider_b])].set_index("rider")
        comparison = comparison[
            [
                "laps",
                "fastest",
                "median",
                "iqr",
                "consistency_score",
                "theoretical_best",
                "potential_lost",
                "top_speed",
            ]
        ].T.astype(object)
        timing_rows = ["fastest", "median", "iqr", "theoretical_best", "potential_lost"]
        if race_time_format:
            comparison.loc[timing_rows] = comparison.loc[timing_rows].map(format_time)
            time_unit = "race format"
        else:
            comparison.loc[timing_rows] = comparison.loc[timing_rows].map(
                lambda value: format_number(value, 3)
            )
            time_unit = "seconds"
        comparison.loc["laps"] = comparison.loc["laps"].map(lambda value: format_number(value, 0))
        comparison.loc["consistency_score"] = comparison.loc["consistency_score"].map(
            lambda value: format_number(value, 1)
        )
        comparison.loc["top_speed"] = comparison.loc["top_speed"].map(
            lambda value: format_number(value, 1)
        )
        comparison = comparison.rename(
            index={
                "laps": "laps (count)",
                "fastest": f"fastest ({time_unit})",
                "median": f"median ({time_unit})",
                "iqr": f"iqr ({time_unit})",
                "consistency_score": "consistency_score (0-100)",
                "theoretical_best": f"theoretical_best ({time_unit})",
                "potential_lost": f"potential_lost ({time_unit})",
                "top_speed": "top_speed (km/h)",
            }
        )
        st.dataframe(comparison, width="stretch")

        comparison_deltas = matched_lap_deltas(selected_laps, rider_a, rider_b)
        delta_chart = px.bar(
            comparison_deltas,
            x="lap",
            y="delta",
            color="delta",
            color_continuous_scale=[
                [0, THEME["cobalt"]],
                [0.5, THEME["line"]],
                [1, THEME["kerb_red"]],
            ],
            color_continuous_midpoint=0,
            title=f"Lap delta · {rider_a} minus {rider_b}",
            labels={"delta": "Delta (seconds)", "lap": "Lap"},
        )

        delta_chart.update_yaxes(tickformat=".3f")
        delta_chart.update_coloraxes(colorbar_tickformat=".3f")

        st.plotly_chart(chart_layout(delta_chart, THEME), width="stretch")

with quality_tab:
    quality = metadata["quality"]
    quality_cards = st.columns(4)
    quality_cards[0].metric("Riders", quality["riders_detected"])
    quality_cards[1].metric("Numbered laps", quality["laps_detected"])
    quality_cards[2].metric("Valid laps", quality["valid_laps"])
    quality_cards[3].metric("Sector completeness", f"{quality['sector_completeness']:.1%}")
    if quality["parser_warnings"]:
        for warning in quality["parser_warnings"]:
            st.warning(warning)
    else:
        st.success("All rider run, lap, full-lap, and valid-lap counts reconcile.")
    st.dataframe(pd.DataFrame(quality["reconciliation"]), hide_index=True, width="stretch")
    st.caption(
        f"Source SHA-256: {metadata['source_sha256']} · "
        f"sector tolerance: {quality['sector_tolerance_seconds']:.3f}s"
    )
