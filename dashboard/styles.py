"""Pure theme, CSS, and Plotly styling for the Streamlit dashboard."""

from __future__ import annotations

import plotly.graph_objects as go

_THEMES = {
    "light": {
        "porcelain": "#f4f7f5",
        "sheet": "#ffffff",
        "graphite": "#18262f",
        "muted": "#60737d",
        "cobalt": "#1457d9",
        "kerb_red": "#e13b32",
        "signal_yellow": "#f2c14e",
        "aluminum": "#d9e3e5",
        "line": "#c3d0d4",
        "instrument": "#18262f",
        "on_instrument": "#ffffff",
        "grid": "rgba(24, 38, 47, .025)",
        "header": "rgba(244, 247, 245, .92)",
        "sidebar": "#e9eff0",
        "sidebar_line": "#b8c7cb",
        "widget_line": "#aebfc4",
        "sidebar_panel": "rgba(255, 255, 255, .55)",
        "soft_shadow": "rgba(24, 38, 47, .08)",
        "accent_line": "rgba(20, 87, 217, .18)",
        "sector_blue": "#477fdc",
        "chart_shadow": "rgba(195, 208, 212, .65)",
        "plot": "#f8faf9",
        "axis_grid": "#d9e3e5",
        "axis_line": "#9eafb5",
    },
    "dark": {
        "porcelain": "#09141a",
        "sheet": "#10232c",
        "graphite": "#e7eff1",
        "muted": "#9eb0b7",
        "cobalt": "#78a8ff",
        "kerb_red": "#ff6b62",
        "signal_yellow": "#f4c95d",
        "aluminum": "#203943",
        "line": "#2b4651",
        "instrument": "#061016",
        "on_instrument": "#edf5f6",
        "grid": "rgba(179, 204, 212, .04)",
        "header": "rgba(9, 20, 26, .92)",
        "sidebar": "#0c1b22",
        "sidebar_line": "#28414b",
        "widget_line": "#38545f",
        "sidebar_panel": "rgba(16, 35, 44, .72)",
        "soft_shadow": "rgba(0, 0, 0, .26)",
        "accent_line": "rgba(120, 168, 255, .25)",
        "sector_blue": "#4f84df",
        "chart_shadow": "rgba(0, 0, 0, .28)",
        "plot": "#0c1b22",
        "axis_grid": "#29434d",
        "axis_line": "#506872",
    },
}


def get_theme(name: str | None) -> dict[str, str]:
    """Resolve Streamlit's current theme name, defaulting safely to light."""

    return _THEMES.get(name or "light", _THEMES["light"])


def theme_css(theme: dict[str, str]) -> str:
    """Expose the active palette to static dashboard CSS as custom properties."""

    return f"""
    <style>
    :root {{
        --porcelain: {theme["porcelain"]};
        --sheet: {theme["sheet"]};
        --graphite: {theme["graphite"]};
        --muted: {theme["muted"]};
        --cobalt: {theme["cobalt"]};
        --kerb-red: {theme["kerb_red"]};
        --signal-yellow: {theme["signal_yellow"]};
        --aluminum: {theme["aluminum"]};
        --line: {theme["line"]};
        --instrument: {theme["instrument"]};
        --on-instrument: {theme["on_instrument"]};
        --grid: {theme["grid"]};
        --header: {theme["header"]};
        --sidebar: {theme["sidebar"]};
        --sidebar-line: {theme["sidebar_line"]};
        --widget-line: {theme["widget_line"]};
        --sidebar-panel: {theme["sidebar_panel"]};
        --soft-shadow: {theme["soft_shadow"]};
        --accent-line: {theme["accent_line"]};
        --sector-blue: {theme["sector_blue"]};
        --chart-shadow: {theme["chart_shadow"]};
    }}
    </style>
    """


DASHBOARD_CSS = """
<style>
.stApp {
    background:
        linear-gradient(90deg, var(--grid) 1px, transparent 1px),
        linear-gradient(var(--grid) 1px, transparent 1px),
        var(--porcelain);
    background-size: 48px 48px;
    color: var(--graphite);
}
[data-testid="stHeader"] { background: var(--header); }
.block-container { max-width: 1480px; padding-top: 2.2rem; padding-bottom: 3rem; }
[data-testid="stSidebar"] {
    background: var(--sidebar);
    border-right: 1px solid var(--sidebar-line);
    color: var(--graphite);
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stCaption { color: var(--graphite); }
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: var(--sheet);
    border-color: var(--widget-line);
    border-radius: 0;
}
[data-testid="stSidebar"] [role="radiogroup"] {
    padding: .25rem;
    border: 1px solid var(--sidebar-line);
    background: var(--sidebar-panel);
}
h1, h2, h3 {
    font-family: "Bahnschrift SemiCondensed", Bahnschrift, "Arial Narrow", sans-serif;
    letter-spacing: -.035em;
}
p, label, [data-testid="stMarkdownContainer"] {
    font-family: Aptos, "Segoe UI", sans-serif;
}
.hero {
    position: relative;
    display: flex;
    grid-template-columns: minmax(180px, 240px) minmax(0, 1fr);
    min-height: 275px;
    overflow: hidden;
    margin: 0 0 1rem;
    border: 1px solid var(--line);
    border-top: 5px solid var(--instrument);
    background: var(--sheet);
    clip-path: polygon(0 0, calc(100% - 38px) 0, 100% 38px, 100% 100%, 0 100%);
    filter: drop-shadow(8px 10px 0 var(--soft-shadow));
}
.session-stamp {
    position: relative;
    z-index: 2;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 1.45rem 1.35rem 1.25rem;
    background: var(--instrument);
    color: var(--on-instrument);
}
.stamp-event,
.stamp-year {
    font: 700 .72rem/1 "Cascadia Mono", Consolas, monospace;
    letter-spacing: .17em;
    text-transform: uppercase;
}
.stamp-session {
    margin: auto 0;
    color: var(--on-instrument);
    font-family: "Bahnschrift SemiCondensed", Bahnschrift, sans-serif;
    font-size: clamp(3.8rem, 7vw, 6.4rem);
    font-weight: 750;
    line-height: .82;
    letter-spacing: -.06em;
}
.stamp-session::after {
    content: "";
    display: block;
    width: 54px;
    height: 7px;
    margin-top: .8rem;
    background: linear-gradient(90deg, var(--cobalt) 0 50%, var(--kerb-red) 50%);
}
.hero-copy {
    position: relative;
    z-index: 2;
    align-self: center;
    min-width: 0;
    padding: 2.15rem clamp(2rem, 5vw, 5.8rem) 2.2rem;
}
.hero-kicker, .data-label {
    color: var(--cobalt);
    font: 700 .7rem/1 "Cascadia Mono", Consolas, monospace;
    letter-spacing: .17em;
    text-transform: uppercase;
}
.hero h1 {
    max-width: 850px;
    margin: .7rem 0 .25rem;
    color: var(--graphite);
    font-size: clamp(2.5rem, 5.4vw, 5.4rem);
    font-weight: 430;
    line-height: .88;
    text-transform: uppercase;
}
.hero h1 span,
.hero h1 strong { display: block; }
.hero h1 strong { color: var(--cobalt); font-weight: 760; }
.hero p {
    max-width: 670px;
    margin: 1rem 0 0;
    color: var(--muted);
    font-size: .96rem;
    line-height: 1.55;
}
.hero-circuit {
    width: min(100%, 760px);
    margin: .65rem 0 0;
}
.hero-circuit img {
    display: block;
    width: 100%;
    height: clamp(128px, 11vw, 165px);
    object-fit: contain;
    object-position: left center;
    filter: drop-shadow(4px 5px 0 var(--soft-shadow));
}
.hero-circuit figcaption {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: .75rem 1.25rem;
    margin-top: .35rem;
    color: var(--muted);
    font: 650 .58rem/1.35 "Cascadia Mono", Consolas, monospace;
    letter-spacing: .05em;
    text-transform: uppercase;
}
.circuit-name {
    flex: 0 0 auto;
    color: var(--graphite);
    font-weight: 750;
}
.circuit-credit { text-align: right; }
.circuit-credit a {
    color: var(--muted);
    text-decoration-color: var(--line);
    text-underline-offset: 2px;
}
.hero-circuit-unavailable {
    margin: 1.25rem 0;
    color: var(--muted);
    font: 700 .72rem/1 "Cascadia Mono", Consolas, monospace;
    letter-spacing: .12em;
    text-transform: uppercase;
}
.hero-empty {
    display: block;
    min-height: auto;
    padding: 2.25rem 2.5rem;
    border-left: 10px solid var(--cobalt);
}
.hero-empty h1 { max-width: 900px; }
.timing-card {
    position: relative;
    min-height: 125px;
    padding: 1.05rem 1.1rem 1rem 1.25rem;
    overflow: hidden;
    border: 1px solid var(--line);
    border-left: 5px solid var(--cobalt);
    background: var(--sheet);
    box-shadow: 5px 6px 0 var(--aluminum);
}
.timing-card::after {
    content: "";
    position: absolute;
    right: -18px;
    top: -30px;
    width: 76px;
    height: 150px;
    border-left: 1px solid var(--accent-line);
    transform: rotate(18deg);
}
.timing-card.caution { border-left-color: var(--signal-yellow); }
.timing-card.signal { border-left-color: var(--kerb-red); }
.timing-card .label {
    color: var(--muted);
    font: 700 .66rem/1.2 "Cascadia Mono", Consolas, monospace;
    letter-spacing: .14em;
    text-transform: uppercase;
}
.timing-card .value {
    margin-top: .72rem;
    color: var(--graphite);
    font-family: "Bahnschrift SemiCondensed", Bahnschrift, sans-serif;
    font-size: clamp(1.3rem, 2.4vw, 2.15rem);
    font-weight: 760;
    line-height: 1;
}
.timing-card .detail { margin-top: .45rem; color: var(--muted); font-size: .78rem; }
[data-testid="stSegmentedControl"],
[data-testid="stButtonGroup"] {
    margin: .85rem 0 1.45rem;
}
[data-testid="stSegmentedControl"] > label,
[data-testid="stButtonGroup"] > label {
    color: var(--cobalt);
    font: 700 .7rem/1 "Cascadia Mono", Consolas, monospace;
    letter-spacing: .17em;
    text-transform: uppercase;
}
[data-testid="stSegmentedControl"] [role="radiogroup"],
[data-testid="stButtonGroup"] [role="radiogroup"] {
    display: flex;
    width: 100%;
    flex-wrap: nowrap !important;
    gap: 1px;
    padding: 1px;
    border: 0;
    border-bottom: 4px solid var(--instrument);
    border-radius: 0;
    background: var(--line);
}
[data-testid="stSegmentedControl"] button,
[data-testid="stSegmentedControl"] [role="radio"],
[data-testid="stButtonGroup"] button,
[data-testid="stButtonGroup"] [role="radio"] {
    flex: 1 1 0;
    min-width: 5rem;
    min-height: 45px;
    border: 0;
    border-radius: 0;
    background: var(--sheet);
    color: var(--muted);
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: .75rem;
    font-weight: 700;
    letter-spacing: .04em;
}
[data-testid="stSegmentedControl"] button[aria-pressed="true"],
[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"],
[data-testid="stButtonGroup"] button[aria-pressed="true"],
[data-testid="stButtonGroup"] [role="radio"][aria-checked="true"] {
    background: var(--instrument);
    color: var(--on-instrument);
    box-shadow: inset 0 -4px 0 var(--cobalt);
}
[data-testid="stSegmentedControl"] button p,
[data-testid="stSegmentedControl"] [role="radio"] p,
[data-testid="stButtonGroup"] button p,
[data-testid="stButtonGroup"] [role="radio"] p { color: inherit; }
div[data-testid="stMetric"] {
    padding: .8rem 1rem;
    background: var(--sheet);
    border: 1px solid var(--line);
    box-shadow: 3px 4px 0 var(--aluminum);
}
div[data-testid="stMetric"] label { color: var(--muted); }
div[data-testid="stMetricValue"] { color: var(--graphite); }
div[data-baseweb="tab-list"] {
    gap: .35rem;
    padding: 0 0 .55rem;
    border-bottom: 2px solid var(--instrument);
}
button[data-baseweb="tab"] {
    min-height: 42px;
    padding: .65rem 1rem;
    border: 1px solid transparent;
    border-radius: 0;
    color: var(--muted);
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: .75rem;
    letter-spacing: .04em;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background: var(--instrument);
    color: var(--on-instrument);
}
button[data-baseweb="tab"][aria-selected="true"] p { color: var(--on-instrument); }
[data-testid="stPlotlyChart"],
[data-testid="stDataFrame"] {
    border: 1px solid var(--line);
    background: var(--sheet);
    box-shadow: 5px 6px 0 var(--chart-shadow);
}
[data-testid="stAlert"] { border-radius: 0; border: 1px solid var(--line); }
[data-testid="stCode"] { border-radius: 0; border: 1px solid var(--line); }
:focus-visible {
    outline: 3px solid var(--signal-yellow) !important;
    outline-offset: 2px;
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; }
}
@media (max-width: 980px) {
    .hero { grid-template-columns: 165px minmax(0, 1fr); }
    .hero-copy { padding-left: 2rem; padding-right: 2rem; }
}
@media (max-width: 720px) {
    .block-container { padding: 1rem .85rem 2rem; }
    .hero { display: block; min-height: auto; clip-path: none; }
    .session-stamp {
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        align-items: center;
        padding: .85rem 1rem;
    }
    .stamp-session { margin: 0; font-size: 2.7rem; text-align: center; }
    .stamp-session::after { display: none; }
    .stamp-year { text-align: right; }
    .hero-copy { padding: 1.5rem 1.15rem 1.7rem; }
    .hero h1 { font-size: clamp(2.45rem, 14vw, 4rem); }
    .hero-circuit { width: 100%; }
    .hero-circuit img {
        height: clamp(155px, 48vw, 220px);
        object-position: center;
    }
    .hero-circuit figcaption { align-items: flex-start; flex-direction: column; }
    .circuit-credit { text-align: left; }
    .hero-empty { padding: 1.5rem 1.15rem; }
    [data-testid="stSegmentedControl"] [role="radiogroup"],
    [data-testid="stButtonGroup"] [role="radiogroup"] { overflow-x: auto; }
    [data-testid="stSegmentedControl"] button,
    [data-testid="stSegmentedControl"] [role="radio"],
    [data-testid="stButtonGroup"] button,
    [data-testid="stButtonGroup"] [role="radio"] { flex: 0 0 auto; white-space: nowrap; }
    div[data-baseweb="tab-list"] { overflow-x: auto; flex-wrap: nowrap; }
    button[data-baseweb="tab"] { white-space: nowrap; }
}
</style>
"""


def chart_colors(
    theme_name: str, theme: dict[str, str]
) -> tuple[dict[str, str], list[str], list[list[float | str]]]:
    """Build constructor, trace, and sector palettes for the active theme."""

    dark_mode = theme_name == "dark"
    constructors = {
        "DUCATI": "#ef4b50" if dark_mode else "#d92f35",
        "KTM": "#ff8a3d" if dark_mode else "#e86e16",
        "APRILIA": "#a985ef" if dark_mode else "#714bbd",
        "YAMAHA": theme["cobalt"],
        "HONDA": "#b8c7cd" if dark_mode else "#465b66",
    }
    traces = [
        theme["cobalt"],
        constructors["DUCATI"],
        constructors["KTM"],
        constructors["APRILIA"],
        constructors["HONDA"],
    ]
    sectors = (
        [[0, "#246a68"], [0.5, "#6a5928"], [1, "#7a363a"]]
        if dark_mode
        else [[0, "#c9e7e4"], [0.5, "#f5e6ad"], [1, "#efb0ab"]]
    )
    return constructors, traces, sectors


def chart_layout(figure: go.Figure, theme: dict[str, str], *, height: int = 500) -> go.Figure:
    """Apply the shared dashboard layout to a Plotly figure."""

    figure.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=45, b=20),
        paper_bgcolor=theme["sheet"],
        plot_bgcolor=theme["plot"],
        font=dict(family="Aptos, Segoe UI", color=theme["muted"]),
        title_font=dict(
            family="Bahnschrift SemiCondensed, Bahnschrift",
            color=theme["graphite"],
            size=23,
        ),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(
            bgcolor=theme["instrument"],
            bordercolor=theme["instrument"],
            font_family="Cascadia Mono, Consolas",
            font_color=theme["on_instrument"],
        ),
    )
    figure.update_xaxes(
        gridcolor=theme["axis_grid"],
        linecolor=theme["axis_line"],
        zerolinecolor=theme["axis_line"],
        tickfont=dict(color=theme["muted"]),
        title_font=dict(color=theme["graphite"]),
    )
    figure.update_yaxes(
        gridcolor=theme["axis_grid"],
        linecolor=theme["axis_line"],
        zerolinecolor=theme["axis_line"],
        tickfont=dict(color=theme["muted"]),
        title_font=dict(color=theme["graphite"]),
    )
    return figure
