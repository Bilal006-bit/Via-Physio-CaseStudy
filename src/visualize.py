"""Visualizations — heatmap and hourly bar chart, saved as PNG to output/."""

import logging
import warnings

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

from src.config import DAY_LABELS, OUT_DIR, OVERLOAD_THRESHOLD, UNDERUTIL_THRESHOLD

logger = logging.getLogger(__name__)


def _save(fig: plt.Figure, name: str) -> None:
    """Save figure to output/ and close it."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved → %s", name)


def _slot_colour(val: float) -> str:
    """Traffic-light colour for a utilization value."""
    if val > OVERLOAD_THRESHOLD:
        return "#e74c3c"  # red — overloaded
    if val >= UNDERUTIL_THRESHOLD:
        return "#f39c12"  # amber — normal
    return "#27ae60"  # green — free capacity


def plot_heatmap(merged: pd.DataFrame) -> None:
    """Heatmap: time slots × weekdays, coloured by utilization ratio.

    RdYlGn_r: red = overloaded, green = free — intuitive for a clinic manager.
    """
    pivot = merged.pivot_table(
        index="time", columns="date", values="utilization", aggfunc="mean"
    )
    pivot.columns = [DAY_LABELS.get(c, c) for c in pivot.columns]

    fig, ax = plt.subplots(figsize=(10, 13))
    sns.heatmap(
        pivot.sort_index(),
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
        "Reception Utilization — KW 35 (25–29 Aug 2025)\nRed = overloaded  |  Green = free",
        fontsize=13,
        fontweight="bold",
        pad=14,
    )
    ax.tick_params(axis="x", rotation=0)
    ax.tick_params(axis="y", rotation=0)
    _save(fig, "heatmap.png")


def plot_hourly_bar(hourly_avg: pd.DataFrame) -> None:
    """Bar chart: average utilization by hour of day across all 5 days.

    Shows *when* the clinic is under pressure — more actionable than daily averages.
    """
    colours = [_slot_colour(v) for v in hourly_avg["utilization"]]
    labels = [f"{int(h):02d}:00" for h in hourly_avg["hour"]]
    x = list(range(len(labels)))

    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(
        x, hourly_avg["utilization"], color=colours, width=0.6, edgecolor="white"
    )
    ax.set_xticks(x)
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
        label=f"Overloaded  (> {OVERLOAD_THRESHOLD})",
    )
    ax.axhline(
        UNDERUTIL_THRESHOLD,
        color="#27ae60",
        linestyle="--",
        linewidth=1.2,
        label=f"Free  (< {UNDERUTIL_THRESHOLD})",
    )
    ax.set_title(
        "Average Utilization by Hour of Day — KW 35", fontsize=13, fontweight="bold"
    )
    ax.set_ylabel("Avg Utilization  (patients ÷ admins)")
    ax.set_ylim(0, max(hourly_avg["utilization"].max() * 1.25, 1.6))
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(axis="x", rotation=45)
    _save(fig, "hourly_bar.png")
