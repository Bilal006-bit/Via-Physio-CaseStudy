"""
Analysis module.

Computes summary statistics from the merged utilization table:
  - Daily and weekly averages
  - Overloaded and underutilised slot lists
  - Hourly aggregation (for the bar chart)
  - Bonus: weekly report metrics
"""

import logging

import pandas as pd

from src.config import (
    OVERLOAD_THRESHOLD,
    UNDERUTIL_THRESHOLD,
    DAY_LABELS,
)

logger = logging.getLogger(__name__)


def daily_averages(merged: pd.DataFrame) -> pd.DataFrame:
    """Return average utilization per day, with readable day labels."""
    valid = merged[merged["utilization"].notna()]
    avg = valid.groupby("date")["utilization"].mean().round(2).reset_index()
    avg["day"] = avg["date"].map(DAY_LABELS)
    return avg.sort_values("date")


def hourly_averages(merged: pd.DataFrame) -> pd.DataFrame:
    """Aggregate 20-min slots to hourly buckets (avg utilization by hour of day).

    Shows *when during the day* reception is under pressure — more actionable
    for an ops manager than the daily view.
    """
    valid = merged[merged["utilization"].notna()].copy()
    valid["hour"] = valid["time"].str[:2].astype(int)
    return (
        valid.groupby("hour")["utilization"]
        .mean()
        .round(2)
        .reset_index()
        .sort_values("hour")
    )


def top_overloaded(merged: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Return the n most overloaded slots, sorted by utilization descending."""
    cols = ["date", "time", "patients_booked", "admins_available", "utilization"]
    return (
        merged[merged["status"] == "Overloaded"][cols]
        .sort_values("utilization", ascending=False)
        .head(n)
    )


def top_free(merged: pd.DataFrame, n: int = 8) -> pd.DataFrame:
    """Return free windows sorted by admin availability then utilization.

    Most valuable windows (2+ admins, 0 patients) appear first.
    """
    cols = ["date", "time", "patients_booked", "admins_available", "utilization"]
    return (
        merged[(merged["status"] == "Underutilised") & (merged["admins_available"] > 0)][
            cols
        ]
        .sort_values(["admins_available", "utilization"], ascending=[False, True])
        .head(n)
    )


def weekly_summary(merged: pd.DataFrame) -> dict:
    """Compute the bonus weekly report metrics."""
    valid = merged[merged["utilization"].notna()]
    total = len(merged)
    counts = merged["status"].value_counts()

    top3 = valid.nlargest(3, "utilization")[
        ["date", "time", "patients_booked", "admins_available", "utilization"]
    ]

    return {
        "weekly_avg": round(valid["utilization"].mean(), 2),
        "total_slots": total,
        "status_counts": counts,
        "pct": {k: round(v / total * 100, 1) for k, v in counts.items()},
        "top3": top3,
    }


def run_analysis(merged: pd.DataFrame) -> dict:
    """Run all analyses and return a single results dict for downstream use."""
    results = {
        "daily_avg": daily_averages(merged),
        "hourly_avg": hourly_averages(merged),
        "overloaded": top_overloaded(merged),
        "free": top_free(merged),
        **weekly_summary(merged),
    }
    logger.info(
        "Analysis complete — weekly avg: %.2f | overloaded: %.1f%%",
        results["weekly_avg"],
        results["pct"].get("Overloaded", 0),
    )
    return results
