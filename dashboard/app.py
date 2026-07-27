from __future__ import annotations

import html
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from motogp_analytics import (
    discover_sessions,
    format_time,
    load_laps,
    rider_summary,
    select_scope,
)

st.set_page_config(
    page_title="MotoGP Pace Lab",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
    :root {
        --track: #08131d;
        --pitwall: #102534;
        --panel: #132d3d;
        --ice: #eaf4f5;
        --muted: #8ba5b2;
        --telemetry: #4ad7d1;
        --caution: #ffc857;
        --signal: #ff4d6d;
    }
    .stApp {
        background:
            linear-gradient(110deg, rgba(74, 215, 209, .035) 1px, transparent 1px),
            var(--track);
        background-size: 42px 42px;
        color: var(--ice);
    }
    .block-container { max-width: 1480px; padding-top: 2rem; }
    [data-testid="stSidebar"] { background: #0b1b27; border-right: 1px solid #214050; }
    h1, h2, h3 {
        font-family: Bahnschrift, "Arial Narrow", sans-serif;
        letter-spacing: -.025em;
    }
    p, label, [data-testid="stMarkdownContainer"] {
        font-family: "Segoe UI", sans-serif;
    }
    .hero {
        position: relative;
        overflow: hidden;
        margin: 0 0 1.2rem;
        padding: 1.7rem 2rem 1.8rem;
        border: 1px solid #214050;
        border-left: 5px solid var(--telemetry);
        background: linear-gradient(105deg, #102534 0%, #0b1b27 72%);
    }
    .hero::after {
        content: "";
        position: absolute;
        width: 280px;
        height: 8px;
        right: -48px;
        top: 52px;
        background: var(--telemetry);
        transform: rotate(-12deg);
        box-shadow: 0 24px 0 var(--signal), 0 48px 0 var(--caution);
        opacity: .8;
    }
    .hero-kicker, .data-label {
        color: var(--telemetry);
        font: 700 .72rem/1 Consolas, monospace;
        letter-spacing: .16em;
        text-transform: uppercase;
    }
    .hero h1 {
        max-width: 760px;
        margin: .45rem 0 .2rem;
        color: var(--ice);
        font-size: clamp(2rem, 5vw, 4.3rem);
        line-height: .95;
        text-transform: uppercase;
    }
    .hero p { max-width: 650px; margin: .8rem 0 0; color: #b7c9d1; }
    .timing-card {
        min-height: 118px;
        padding: 1rem 1.1rem;
        border-top: 3px solid var(--telemetry);
        background: var(--pitwall);
        box-shadow: inset 0 0 0 1px #214050;
    }
    .timing-card.caution { border-top-color: var(--caution); }
    .timing-card.signal { border-top-color: var(--signal); }
    .timing-card .label {
        color: var(--muted);
        font: 700 .68rem/1.2 Consolas, monospace;
        letter-spacing: .12em;
        text-transform: uppercase;
    }
    .timing-card .value {
        margin-top: .65rem;
        color: var(--ice);
        font: 700 clamp(1.25rem, 2.4vw, 2rem)/1 Bahnschrift, sans-serif;
    }
    .timing-card .detail { margin-top: .45rem; color: var(--muted); font-size: .78rem; }
    .sector-ribbon {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 2px;
        margin: .8rem 0 1.4rem;
    }
    .sector-ribbon span {
        padding: .48rem .7rem;
        background: #163748;
        color: #a9bdc6;
        font: 700 .68rem/1 Consolas, monospace;
        letter-spacing: .1em;
        text-align: center;
    }
    .sector-ribbon span:nth-child(1) { border-bottom: 3px solid #4ad7d1; }
    .sector-ribbon span:nth-child(2) { border-bottom: 3px solid #78a9ff; }
    .sector-ribbon span:nth-child(3) { border-bottom: 3px solid #ffc857; }
    .sector-ribbon span:nth-child(4) { border-bottom: 3px solid #ff4d6d; }
    div[data-testid="stMetric"] { background: var(--pitwall); border: 1px solid #214050; }
    div[data-baseweb="tab-list"] { gap: .25rem; border-bottom: 1px solid #214050; }
    button[data-baseweb="tab"] { font-family: Consolas, monospace; }
    :focus-visible { outline: 2px solid var(--caution) !important; outline-offset: 2px; }
    @media (max-width: 720px) {
        .block-container { padding: 1rem; }
        .hero { padding: 1.25rem; }
        .hero::after { opacity: .25; }
        .sector-ribbon { grid-template-columns: repeat(2, 1fr); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

DATA_ROOT = Path(os.environ.get("MOTOGP_DATA_ROOT", "data"))
CONSTRUCTOR_COLORS = {
    "DUCATI": "#ff4d6d",
    "KTM": "#ff8c42",
    "APRILIA": "#b18cff",
    "YAMAHA": "#78a9ff",
    "HONDA": "#eaf4f5",
}


@st.cache_data(show_spinner=False)
def read_laps(path: str, modified: float) -> pd.DataFrame:
    del modified
    return load_laps(path)


def session_label(path: Path) -> str:
    values = {part.split("=", 1)[0]: part.split("=", 1)[1] for part in path.parts if "=" in part}
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


def chart_layout(figure: go.Figure, *, height: int = 500) -> go.Figure:
    figure.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=45, b=20),
        paper_bgcolor="#102534",
        plot_bgcolor="#102534",
        font=dict(family="Segoe UI", color="#b7c9d1"),
        title_font=dict(family="Bahnschrift", color="#eaf4f5", size=22),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#08131d", font_family="Consolas"),
    )
    figure.update_xaxes(gridcolor="#214050", zerolinecolor="#214050")
    figure.update_yaxes(gridcolor="#214050", zerolinecolor="#214050")
    return figure


sessions = discover_sessions(DATA_ROOT)
if not sessions:
    st.markdown(
        """
        <div class="hero">
            <div class="hero-kicker">No timing feed</div>
            <h1>Ingest one session to light the pit wall.</h1>
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

metadata_path = selected_path / "session.json"
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
laps_path = selected_path / "laps.parquet"
laps = read_laps(str(selected_path), laps_path.stat().st_mtime)
summary = rider_summary(laps, scope=scope)
selected_laps = select_scope(laps, scope)

st.markdown(
    f"""
    <div class="hero">
        <div class="hero-kicker">{html.escape(session_label(selected_path))} · {scope} pace</div>
        <h1>Find the pace the classification hides.</h1>
        <p>Compare repeatable lap speed, sector contribution, and execution potential from the
        official timing analysis.</p>
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

fastest = summary.loc[summary["fastest"].idxmin()]
best_median = summary.loc[summary["median"].idxmin()]
consistent_pool = summary[summary["laps"] >= 3]
most_consistent = (
    consistent_pool.loc[consistent_pool["iqr"].idxmin()] if not consistent_pool.empty else None
)
speed_pool = summary.dropna(subset=["top_speed"])
top_speed = speed_pool.loc[speed_pool["top_speed"].idxmax()] if not speed_pool.empty else None

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
                marker_color=CONSTRUCTOR_COLORS.get(constructor, "#4ad7d1"),
                boxpoints=False,
                hovertemplate=f"{rider}<br>%{{x:.3f}}s<extra></extra>",
            )
        )
    pace.update_layout(title="Repeatable pace window", showlegend=False)
    pace.update_yaxes(categoryorder="array", categoryarray=list(reversed(order)))
    pace.update_xaxes(title="Lap time (seconds)")
    st.plotly_chart(chart_layout(pace, height=max(520, len(order) * 29)), width="stretch")

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
        color_discrete_sequence=["#4ad7d1", "#ffc857", "#ff4d6d", "#78a9ff", "#b18cff"],
        title="Lap-time evolution",
        labels={"lap_time_seconds": "Lap time (seconds)", "lap": "Lap"},
    )
    st.plotly_chart(chart_layout(evolution), width="stretch")

with sector_tab:
    sector_columns = ["median_t1", "median_t2", "median_t3", "median_t4"]
    sector_values = summary.set_index("rider")[sector_columns]
    deltas = sector_values - sector_values.min(axis=0)
    if deltas.dropna(how="all").empty:
        st.info("No complete, valid sector observations are available.")
    else:
        heatmap = go.Figure(
            go.Heatmap(
                z=deltas.to_numpy(),
                x=["T1", "T2", "T3", "T4"],
                y=deltas.index,
                colorscale=[[0, "#4ad7d1"], [0.45, "#214f62"], [1, "#ff4d6d"]],
                colorbar=dict(title="Delta (s)"),
                texttemplate="+%{z:.3f}",
                hovertemplate="%{y}<br>%{x}: +%{z:.3f}s<extra></extra>",
            )
        )
        heatmap.update_layout(title="Median sector deficit to benchmark")
        st.plotly_chart(chart_layout(heatmap, height=max(520, len(summary) * 29)), width="stretch")

    theory = summary[["rider", "fastest", "theoretical_best", "potential_lost"]].copy()
    theory["fastest"] = summary["theoretical_reference"]
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
        comparison = summary[summary["rider"].isin([rider_a, rider_b])].set_index("rider")
        comparison = comparison[
            [
                "laps",
                "fastest",
                "median",
                "iqr",
                "theoretical_best",
                "potential_lost",
                "top_speed",
            ]
        ].T
        st.dataframe(comparison, width="stretch")

        a_laps = selected_laps[selected_laps["rider"] == rider_a][["lap", "lap_time_seconds"]]
        b_laps = selected_laps[selected_laps["rider"] == rider_b][["lap", "lap_time_seconds"]]
        comparison_deltas = a_laps.merge(b_laps, on="lap", suffixes=("_a", "_b"))
        comparison_deltas["delta"] = (
            comparison_deltas["lap_time_seconds_a"] - comparison_deltas["lap_time_seconds_b"]
        )
        delta_chart = px.bar(
            comparison_deltas,
            x="lap",
            y="delta",
            color="delta",
            color_continuous_scale=[
                [0, "#4ad7d1"],
                [0.5, "#214050"],
                [1, "#ff4d6d"],
            ],
            color_continuous_midpoint=0,
            title=f"Lap delta · {rider_a} minus {rider_b}",
            labels={"delta": "Delta (seconds)", "lap": "Lap"},
        )
        st.plotly_chart(chart_layout(delta_chart), width="stretch")

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
