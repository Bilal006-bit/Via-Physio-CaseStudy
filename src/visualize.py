"""
Visualization module — Plotly interactive charts.

Returns HTML div strings embedded in summary_report.html.
Charts are fully interactive: hover, zoom, tooltips.
"""

import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.config import DAY_LABELS, OVERLOAD_THRESHOLD, UNDERUTIL_THRESHOLD

logger = logging.getLogger(__name__)


# ── Discrete 4-zone colorscale ─────────────────────────────────────────────────
# zmin = -0.5 (No Coverage sentinel)  zmax = 2.5
# Normalised range = 3.0
# -0.5 → 0.0  :  gray   (No Coverage)   0/3 → 0.166
#  0.0 → 0.5  :  green  (Free)          0.5/3 → 0.167 → 0.333
#  0.5 → 1.0  :  amber  (Normal)        1.5/3 → 0.333 → 0.500
#  1.0 → 2.5  :  red    (Overloaded)    2.0/3 → 0.500 → 1.000
_COLORSCALE = [
    [0.000, "#bdc3c7"],  # gray  — No Coverage
    [0.166, "#bdc3c7"],
    [0.167, "#27ae60"],  # green — Free
    [0.332, "#27ae60"],
    [0.333, "#f39c12"],  # amber — Normal
    [0.499, "#f39c12"],
    [0.500, "#e74c3c"],  # red   — Overloaded
    [1.000, "#8b0000"],  # dark red at ratio 2.5
]

_COLORBAR = dict(
    tickvals=[-0.5, 0.0, 0.5, 1.0, 2.5],
    ticktext=[
        "No Coverage  (NC)",
        "0.0  —  Free starts",
        "0.5  —  Normal starts",
        "1.0  —  Overloaded starts",
        "2.5+",
    ],
    title=dict(text="Utilization Ratio", side="right", font=dict(size=11)),
    thickness=20,
    len=0.95,
    tickfont=dict(size=10),
)


def _slot_colour(val: float) -> str:
    """Traffic-light colour for a single utilization value (bar chart)."""
    if val > OVERLOAD_THRESHOLD:
        return "#e74c3c"
    if val >= UNDERUTIL_THRESHOLD:
        return "#f39c12"
    return "#27ae60"


def _fmt_cell(v, p, a) -> str:
    """Cell display text — no NaN shown to end users."""
    if p == 0 and a == 0:
        return ""  # truly empty → blank
    if a == 0 and p > 0:
        return "NC"  # No Coverage → abbreviated label
    if np.isnan(v):
        return "—"
    return f"{v:.1f}"  # one decimal keeps cells uncluttered


def _fmt_tooltip(v, p, a) -> str:
    """Full tooltip text for hover."""
    if p == 0 and a == 0:
        return "No data"
    if a == 0 and p > 0:
        return "No Coverage — no admin scheduled"
    if np.isnan(v):
        return "—"
    return f"{v:.2f}"


def heatmap_div(merged: pd.DataFrame, first_chart: bool = True) -> str:
    """Interactive heatmap: hourly buckets × days, coloured by utilization ratio.

    Aggregates 20-min slots → 1-hour buckets (mean) for a readable grid (~13 rows).
    Fixes applied:
      - No Coverage cells shown as gray with 'NC' label (not 'NaN')
      - Discrete 4-colour zones with labeled colorbar (gray/green/amber/red)
      - Hover tooltip shows status, avg ratio, total patients, avg admins
    """
    # ── Aggregate 20-min slots → 1-hour buckets ────────────────────────────────
    df = merged.copy()
    df["hour"] = df["time"].str[:2].astype(int)
    df["hour_label"] = df["hour"].apply(lambda h: f"{h:02d}:00 – {h:02d}:59")

    util = df.pivot_table(
        index="hour_label", columns="date", values="utilization", aggfunc="mean"
    ).sort_index()
    pts = (
        df.pivot_table(
            index="hour_label", columns="date", values="patients_booked", aggfunc="sum"
        )
        .reindex_like(util)
        .fillna(0)
    )
    adm = (
        df.pivot_table(
            index="hour_label", columns="date", values="admins_available", aggfunc="mean"
        )
        .reindex_like(util)
        .fillna(0)
    )

    # ── Filter: drop hours with zero activity on every day ─────────────────────
    active = (pts.values > 0).any(axis=1) | (adm.values > 0).any(axis=1)
    util = util[active]
    pts = pts[active]
    adm = adm[active]

    day_labels = [DAY_LABELS.get(c, c) for c in util.columns]
    time_labels = util.index.tolist()
    n_rows = len(time_labels)

    # ── Display array: -0.5 sentinel for No Coverage, NaN stays for blank ──────
    z_display = util.values.copy().astype(float)
    no_cover_mask = (adm.values == 0) & (pts.values > 0)
    z_display[no_cover_mask] = -0.5

    # ── Cell text and tooltip text ──────────────────────────────────────────────
    cell_text = np.vectorize(_fmt_cell)(util.values, pts.values, adm.values)
    tooltip_text = np.vectorize(_fmt_tooltip)(util.values, pts.values, adm.values)
    custom = np.stack([pts.values, adm.values, tooltip_text], axis=-1)

    # ── Build figure ────────────────────────────────────────────────────────────
    fig = go.Figure(
        data=go.Heatmap(
            z=z_display,
            x=day_labels,
            y=time_labels,
            colorscale=_COLORSCALE,
            zmin=-0.5,
            zmax=2.5,
            text=cell_text,
            texttemplate="%{text}",
            textfont={"size": 10, "color": "#ffffff"},
            customdata=custom,
            hovertemplate=(
                "<b>%{x}  ·  %{y}</b><br>"
                "Utilization: <b>%{customdata[2]}</b><br>"
                "Patients booked: %{customdata[0]:.0f}<br>"
                "Admins available: %{customdata[1]:.0f}"
                "<extra></extra>"
            ),
            colorbar=_COLORBAR,
        )
    )

    fig.update_layout(
        title=dict(
            text=(
                "Reception Utilization — KW 35  (Mon 25 – Fri 29 Aug 2025)<br>"
                "<sup style='color:#666'>Hover any cell for details  "
                "·  Gray = no admin scheduled  "
                "·  Green = free  "
                "·  Amber = normal  "
                "·  Red = overloaded</sup>"
            ),
            font=dict(size=14, color="#23285D"),
            y=0.98,
        ),
        xaxis=dict(
            title="",
            tickfont=dict(size=12, color="#23285D", family="Arial"),
            side="top",
            fixedrange=True,
        ),
        yaxis=dict(
            title="Time Slot",
            autorange="reversed",
            tickfont=dict(size=9),
            fixedrange=True,
        ),
        font=dict(family="Arial"),
        height=max(460, n_rows * 42),  # 42px per row — more breathing room
        margin=dict(l=130, r=185, t=110, b=30),  # l=130 fits "07:00 – 07:59"
        plot_bgcolor="#eaecee",   # light grey fills empty (no-data) cells cleanly
        paper_bgcolor="#ffffff",
    )

    div = fig.to_html(
        full_html=False,
        include_plotlyjs=first_chart,
        config={"responsive": True, "displayModeBar": True, "displaylogo": False},
    )
    logger.info("Heatmap generated — %d rows × %d cols", n_rows, len(day_labels))
    return div


def hourly_bar_div(hourly_avg: pd.DataFrame) -> str:
    """Interactive bar chart: avg utilization by hour of day (all 5 days).

    Bars colour-coded by zone. Hover shows exact ratio.
    Assumes plotly.js already embedded (call after heatmap_div).
    """
    colours = [_slot_colour(v) for v in hourly_avg["utilization"]]
    labels = [f"{int(h):02d}:00" for h in hourly_avg["hour"]]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=labels,
            y=hourly_avg["utilization"].tolist(),
            marker_color=colours,
            marker_line_color="white",
            marker_line_width=1.5,
            hovertemplate=(
                "<b>%{x}</b><br>" "Avg ratio: <b>%{y:.2f}</b><br>" "<extra></extra>"
            ),
            text=[f"{v:.2f}" for v in hourly_avg["utilization"]],
            textposition="outside",
            textfont=dict(size=9, color="#333"),
        )
    )

    fig.add_hline(
        y=OVERLOAD_THRESHOLD,
        line=dict(color="#e74c3c", dash="dash", width=1.5),
        annotation_text="Overloaded threshold (1.0)",
        annotation_position="top left",
        annotation_font=dict(color="#e74c3c", size=10),
    )
    fig.add_hline(
        y=UNDERUTIL_THRESHOLD,
        line=dict(color="#27ae60", dash="dash", width=1.5),
        annotation_text="Free capacity threshold (0.5)",
        annotation_position="bottom left",
        annotation_font=dict(color="#27ae60", size=10),
    )

    # Shaded background zones for clarity
    fig.add_hrect(
        y0=0, y1=0.5, fillcolor="#27ae60", opacity=0.06, layer="below", line_width=0
    )
    fig.add_hrect(
        y0=0.5, y1=1.0, fillcolor="#f39c12", opacity=0.06, layer="below", line_width=0
    )
    fig.add_hrect(
        y0=1.0,
        y1=hourly_avg["utilization"].max() * 1.3,
        fillcolor="#e74c3c",
        opacity=0.06,
        layer="below",
        line_width=0,
    )

    fig.update_layout(
        title=dict(
            text="Average Utilization by Hour of Day — KW 35 (all 5 days combined)",
            font=dict(size=14, color="#23285D"),
        ),
        xaxis=dict(title="Hour of Day", tickfont=dict(size=10)),
        yaxis=dict(
            title="Avg Utilization  (patients ÷ admins)",
            tickfont=dict(size=10),
            rangemode="tozero",
        ),
        font=dict(family="Arial"),
        height=420,
        margin=dict(l=70, r=20, t=70, b=50),
        plot_bgcolor="#fafafa",
        paper_bgcolor="#ffffff",
        showlegend=False,
        bargap=0.25,
    )

    div = fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"responsive": True, "displaylogo": False},
    )
    logger.info("Hourly bar generated")
    return div
