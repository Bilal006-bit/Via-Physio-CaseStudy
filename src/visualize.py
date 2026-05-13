"""
Visualization module.

Produces two charts saved as PNG to output/:
  1. heatmap.png   — utilization by time slot × day  (REQUIRED)
  2. hourly_bar.png — avg utilization by hour of day  (OPTIONAL but adds value)

Colour logic (RdYlGn_r):
  Red   = overloaded  (ratio > 1.0)
  Yellow = normal     (ratio ~0.5–1.0)
  Green  = free       (ratio < 0.5)

RdYlGn_r maps intuitively to a clinic manager's mental model
("red = problem, green = capacity to use").
"""

import logging
import warnings

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

from src.config import DAY_LABELS, OUT_DIR, OVERLOAD_THRESHOLD, UNDERUTIL_THRESHOLD

logger = logging.getLogger(__name__)


def _save(fig: plt.Figure, filename: str) -> None:
    """Save figure to output directory and close it."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / filename
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved → %s", path.name)


def plot_heatmap(merged: pd.DataFrame) -> None:
    """Heatmap: time slots (rows) x weekdays (columns), colour = utilization ratio.

    Uses RdYlGn_r so red = overloaded and green = free capacity —
    immediately readable for a clinic operations manager.
    """
    pivot = merged.pivot_table(
        index="time", columns="date", values="utilization", aggfunc="mean"
    )
    pivot.columns = [DAY_LABELS.get(c, c) for c in pivot.columns]
    pivot = pivot.sort_index()

    fig, ax = plt.subplots(figsize=(10, 13))
    sns.heatmap(
        pivot,
        ax=ax,
        cmap="RdYlGn_r",
        vmin=0,
        vmax=2.5,
        center=1.0,
        annot=True,
        fmt=".1f",
        linewidths=0.4,
        linecolor="white",
        cbar_kws={"label": "Utilization Ratio  (patients ÷ admins)"},
    )
    ax.set_title(
        "Reception Utilization Heatmap\n"
        "Via Physiotherapy — KW 35 (25–29 Aug 2025)\n"
        "Red = overloaded  |  Green = free capacity",
        fontsize=13,
        fontweight="bold",
        pad=14,
    )
    ax.set_xlabel("Day", fontsize=11)
    ax.set_ylabel("Time Slot", fontsize=11)
    ax.tick_params(axis="x", rotation=0)
    ax.tick_params(axis="y", rotation=0)

    _save(fig, "heatmap.png")


def plot_hourly_bar(hourly_avg: pd.DataFrame) -> None:
    """Bar chart: average utilization by hour of day (across all 5 days).

    More operationally useful than the daily view — it immediately shows
    *when during the day* the clinic is under pressure.
    """

    def _colour(val: float) -> str:
        """Map utilization value to a traffic-light colour."""
        if val > OVERLOAD_THRESHOLD:
            return "#e74c3c"  # red
        if val >= UNDERUTIL_THRESHOLD:
            return "#f39c12"  # amber / normal
        return "#27ae60"  # green

    colours = [_colour(v) for v in hourly_avg["utilization"]]
    labels = [f"{int(h):02d}:00" for h in hourly_avg["hour"]]
    x_pos = list(range(len(labels)))  # numeric positions avoid categorical warning

    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(
        x_pos, hourly_avg["utilization"], color=colours, width=0.6, edgecolor="white"
    )
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels)

    for bar, val in zip(bars, hourly_avg["utilization"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.03,
            f"{val:.2f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
        )

    ax.axhline(
        OVERLOAD_THRESHOLD,
        color="#e74c3c",
        linestyle="--",
        linewidth=1.2,
        label=f"Overloaded  (>{OVERLOAD_THRESHOLD})",
    )
    ax.axhline(
        UNDERUTIL_THRESHOLD,
        color="#27ae60",
        linestyle="--",
        linewidth=1.2,
        label=f"Free  (<{UNDERUTIL_THRESHOLD})",
    )

    ax.set_title(
        "Average Utilization by Hour of Day\n"
        "Via Physiotherapy — KW 35 (all 5 days combined)",
        fontsize=13,
        fontweight="bold",
    )
    ax.set_xlabel("Hour", fontsize=10)
    ax.set_ylabel("Avg Utilization  (patients ÷ admins)", fontsize=10)
    ax.set_ylim(0, max(hourly_avg["utilization"].max() * 1.25, OVERLOAD_THRESHOLD * 1.4))
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(axis="x", rotation=45)

    _save(fig, "hourly_bar.png")
