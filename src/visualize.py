"""
Visualization module — Plotly interactive charts.

Returns HTML div strings (not PNG files) so the report
embeds fully interactive charts with hover tooltips.

Charts produced:
  1. heatmap_div   — utilization by time slot x day (RdYlGn_r)
  2. hourly_div    — avg utilization by hour of day
"""

import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.config import DAY_LABELS, OVERLOAD_THRESHOLD, UNDERUTIL_THRESHOLD

logger = logging.getLogger(__name__)

# ── Colour helpers ─────────────────────────────────────────────────────────────
_RAMP = [
    [0.0, "#27ae60"],  # green  — free
    [0.4, "#f1c40f"],  # yellow — normal-low
    [0.6, "#e67e22"],  # amber  — normal-high
    [1.0, "#e74c3c"],  # red    — overloaded
]


def _slot_colour(val: float) -> str:
    """Traffic-light hex for a single utilization value (used in bar chart)."""
    if val > OVERLOAD_THRESHOLD:
        return "#e74c3c"
    if val >= UNDERUTIL_THRESHOLD:
        return "#f39c12"
    return "#27ae60"


# ── Chart builders ─────────────────────────────────────────────────────────────


def heatmap_div(merged: pd.DataFrame, first_chart: bool = True) -> str:
    """Interactive heatmap: time slots × days, colour = utilization ratio.

    Hover tooltip shows: day, time, ratio, patient count, admin count.
    first_chart=True  → embeds the plotly.js library (self-contained).
    first_chart=False → returns only the <div> (JS already in page).
    """
    # Build pivot tables — utilization, patients, admins
    util = merged.pivot_table(
        index="time", columns="date", values="utilization", aggfunc="mean"
    ).sort_index()
    pts = (
        merged.pivot_table(
            index="time", columns="date", values="patients_booked", aggfunc="sum"
        )
        .reindex_like(util)
        .fillna(0)
    )
    adm = (
        merged.pivot_table(
            index="time", columns="date", values="admins_available", aggfunc="mean"
        )
        .reindex_like(util)
        .fillna(0)
    )

    day_labels = [DAY_LABELS.get(c, c) for c in util.columns]
    time_labels = util.index.tolist()

    # customdata shape: (rows, cols, 2) → [patients, admins]
    custom = np.stack([pts.values, adm.values], axis=-1)

    fig = go.Figure(
        data=go.Heatmap(
            z=util.values,
            x=day_labels,
            y=time_labels,
            colorscale=_RAMP,
            zmin=0,
            zmax=2.5,
            zmid=1.0,
            text=np.where(np.isnan(util.values), "", util.values),
            texttemplate="%{text:.1f}",
            textfont={"size": 9},
            customdata=custom,
            hovertemplate=(
                "<b>%{x}  ·  %{y}</b><br>"
                "Utilization ratio: <b>%{z:.2f}</b><br>"
                "Patients booked: %{customdata[0]:.0f}<br>"
                "Admins available: %{customdata[1]:.0f}"
                "<extra></extra>"
            ),
            colorbar=dict(
                title=dict(text="Utilization<br>Ratio", side="right"),
                thickness=14,
                len=0.9,
            ),
        )
    )

    fig.update_layout(
        title=dict(
            text="Reception Utilization Heatmap — KW 35 (25–29 Aug 2025)<br>"
            "<sup>Red = overloaded (>1.0)  |  Green = free capacity (<0.5)</sup>",
            font=dict(size=14, color="#23285D"),
        ),
        xaxis=dict(
            title="Day",
            tickfont=dict(size=11),
            side="top",
        ),
        yaxis=dict(
            title="Time Slot",
            autorange="reversed",  # earliest time at top
            tickfont=dict(size=9),
        ),
        font=dict(family="Arial"),
        height=700,
        margin=dict(l=70, r=20, t=90, b=20),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
    )

    div = fig.to_html(
        full_html=False,
        include_plotlyjs=first_chart,  # True = embed ~3.5MB JS once
        config={"responsive": True, "displayModeBar": True},
    )
    logger.info("Heatmap chart div generated (%d chars)", len(div))
    return div


def hourly_bar_div(hourly_avg: pd.DataFrame) -> str:
    """Interactive bar chart: avg utilization by hour of day (all 5 days combined).

    Bars coloured by utilization level. Hover shows exact ratio.
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
            hovertemplate="<b>%{x}</b><br>Avg ratio: <b>%{y:.2f}</b><extra></extra>",
            text=[f"{v:.2f}" for v in hourly_avg["utilization"]],
            textposition="outside",
            textfont=dict(size=9, color="#333"),
        )
    )

    # Threshold lines
    fig.add_hline(
        y=OVERLOAD_THRESHOLD,
        line=dict(color="#e74c3c", dash="dash", width=1.5),
        annotation_text=f"Overloaded  > {OVERLOAD_THRESHOLD}",
        annotation_position="top right",
        annotation_font=dict(color="#e74c3c", size=10),
    )
    fig.add_hline(
        y=UNDERUTIL_THRESHOLD,
        line=dict(color="#27ae60", dash="dash", width=1.5),
        annotation_text=f"Free  < {UNDERUTIL_THRESHOLD}",
        annotation_position="bottom right",
        annotation_font=dict(color="#27ae60", size=10),
    )

    fig.update_layout(
        title=dict(
            text="Average Utilization by Hour of Day — KW 35 (all 5 days combined)",
            font=dict(size=14, color="#23285D"),
        ),
        xaxis=dict(title="Hour of Day", tickfont=dict(size=10)),
        yaxis=dict(
            title="Avg Utilization (patients ÷ admins)",
            tickfont=dict(size=10),
            rangemode="tozero",
        ),
        font=dict(family="Arial"),
        height=400,
        margin=dict(l=60, r=20, t=70, b=50),
        plot_bgcolor="#fafafa",
        paper_bgcolor="#ffffff",
        showlegend=False,
        bargap=0.25,
    )

    div = fig.to_html(
        full_html=False,
        include_plotlyjs=False,  # JS already embedded by heatmap_div
        config={"responsive": True},
    )
    logger.info("Hourly bar chart div generated (%d chars)", len(div))
    return div
