from __future__ import annotations

import html
import os
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.circuits import CIRCUITS, circuit_image_uri
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
    select_full_session_riders,
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

SESSION_ORDER = ("FP1", "PR", "FP2", "FP3", "Q", "Q1", "Q2", "SPR", "WUP", "RAC")
SESSION_LABELS = {
    "PR": "Practice",
    "Q": "Qualifying",
    "SPR": "Sprint",
    "WUP": "Warm Up",
    "RAC": "Race",
}


@st.cache_data(show_spinner=False)
def read_laps(path: str, modified: float) -> pd.DataFrame:
    del modified
    return load_laps(path)


def session_values(path: Path) -> dict[str, str]:
    return {part.split("=", 1)[0]: part.split("=", 1)[1] for part in path.parts if "=" in part}


def default_session(sessions: list[str]) -> str:
    for preferred in ("RAC", "FP1"):
        if preferred in sessions:
            return preferred
    return sessions[0]


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

event_sessions: dict[str, dict[str, Path]] = {}
event_values: dict[str, tuple[str, str]] = {}
for path in sessions:
    values = session_values(path)
    event_id = f"{values['year']}-{values['event'].lower()}"
    event_sessions.setdefault(event_id, {})[values["session"]] = path
    event_values[event_id] = (values["year"], values["event"])

event_venues = {
    event_id: (
        (CIRCUITS[event].country, CIRCUITS[event].venue) if event in CIRCUITS else (event, event)
    )
    for event_id, (_, event) in event_values.items()
}
country_counts = Counter(
    (event_values[event_id][0], country) for event_id, (country, _) in event_venues.items()
)
event_names = {
    event_id: (
        f"{country} - {track}"
        if country_counts[(event_values[event_id][0], country)] > 1
        else country
    )
    for event_id, (country, track) in event_venues.items()
}
event_labels = {
    event_id: f"{event_values[event_id][0]} {event_names[event_id]}" for event_id in event_sessions
}
event_ids = list(event_sessions)

requested_event = st.query_params.get("event")
requested_event = requested_event.lower() if requested_event else None
requested_session = st.query_params.get("session")
requested_session = requested_session.upper() if requested_session else None
initial_event = requested_event if requested_event in event_sessions else event_ids[0]
query_state = (requested_event, requested_session)
previous_query_state = st.session_state.get("_query_state")
query_changed = previous_query_state is not None and query_state != previous_query_state
event_index = event_ids.index(initial_event)
if query_changed:
    st.session_state["selected_event"] = initial_event
    event_index = None

with st.sidebar:
    st.markdown('<div class="data-label">Timing feed</div>', unsafe_allow_html=True)
    selected_event_id = st.selectbox(
        "Event",
        event_ids,
        index=event_index,
        format_func=event_labels.__getitem__,
        key="selected_event",
    )
    available_sessions = sorted(
        event_sessions[selected_event_id],
        key=lambda code: SESSION_ORDER.index(code) if code in SESSION_ORDER else len(SESSION_ORDER),
    )
    event_changed = st.session_state.get("_session_event") != selected_event_id
    query_controls_state = previous_query_state is None or query_changed
    if event_changed:
        linked_session = (
            requested_session
            if query_controls_state and requested_event == selected_event_id
            else None
        )
        st.session_state["selected_session"] = (
            linked_session
            if linked_session in available_sessions
            else default_session(available_sessions)
        )
        st.session_state["_session_event"] = selected_event_id
    elif query_changed:
        st.session_state["selected_session"] = (
            requested_session
            if requested_session in available_sessions
            else default_session(available_sessions)
        )
    elif st.session_state.get("selected_session") not in available_sessions:
        previous_session = st.session_state.get("_last_session")
        st.session_state["selected_session"] = (
            previous_session
            if previous_session in available_sessions
            else default_session(available_sessions)
        )

    selected_session = st.session_state["selected_session"]
    st.session_state["_last_session"] = selected_session
    selected_path = event_sessions[selected_event_id][selected_session]
    session = session_values(selected_path)
    scope = st.radio("Pace view", ["clean", "raw"], horizontal=True)
    exclude_incomplete_riders = False
    if selected_session in {"SPR", "RAC"}:
        exclude_incomplete_riders = st.toggle(
            "Exclude incomplete riders",
            help="Keep only riders who recorded every lap of the Sprint or Grand Prix distance.",
            key="exclude_incomplete_riders",
        )
    st.caption(
        "Clean excludes opening, out, pit, cancelled, incomplete, and anomalously slow laps."
    )
    st.caption("Sector potential always uses complete, officially valid timing observations.")

if requested_event != selected_event_id:
    st.query_params["event"] = selected_event_id
if requested_session != selected_session:
    st.query_params["session"] = selected_session
st.session_state["_query_state"] = (selected_event_id, selected_session)

metadata = load_session_metadata(selected_path)
laps_path = selected_path / "laps.parquet"
laps = read_laps(str(selected_path), laps_path.stat().st_mtime)
analysis_laps = select_full_session_riders(laps) if exclude_incomplete_riders else laps
summary = rider_summary(analysis_laps, scope=scope)
selected_laps = select_scope(analysis_laps, scope)
session_display = SESSION_LABELS.get(selected_session, selected_session).upper()
event_code = event_values[selected_event_id][1]
circuit = CIRCUITS.get(event_code)
circuit_uri = circuit_image_uri(event_code, THEME["graphite"], THEME["cobalt"])
if circuit and circuit_uri:
    circuit_map = f"""
        <figure class="hero-circuit">
            <img src="{circuit_uri}" alt="{html.escape(circuit.venue)} circuit layout" />
            <figcaption>
                <span class="circuit-name">{html.escape(circuit.venue)} circuit</span>
                <span class="circuit-credit">Artwork: <a href="{html.escape(circuit.source_url)}"
                      target="_blank" rel="noopener noreferrer">{html.escape(circuit.credit)}</a>
                      · <a href="{html.escape(circuit.license_url)}" target="_blank"
                      rel="noopener noreferrer">{html.escape(circuit.license_name)}</a></span>
            </figcaption>
        </figure>
    """
else:
    circuit_map = '<div class="hero-circuit-unavailable">Circuit map unavailable</div>'

st.markdown(
    f"""
    <div class="hero">
         <div class="session-stamp">
             <div class="stamp-event">{html.escape(event_names[selected_event_id])} · MotoGP</div>
             <div class="stamp-session">{html.escape(session_display)}</div>
             <div class="stamp-year">{html.escape(session["year"])}</div>
        </div>
        <div class="hero-copy">
            <div class="hero-kicker">Performance analysis · {html.escape(scope)} pace</div>
            <div>{circuit_map}</div>
            <p>Compare repeatable lap speed, sector contribution, and execution potential from
            the official timing analysis.</p>
        </div>
     </div>
     """,
    unsafe_allow_html=True,
)

st.segmented_control(
    "Session",
    available_sessions,
    format_func=lambda code: SESSION_LABELS.get(code, code),
    key="selected_session",
    width="stretch",
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
            key="race_time_format",
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
