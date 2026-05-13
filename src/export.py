"""
Export module.

Writes analysis outputs to output/:
  - merged_utilization.csv   full merged dataset with ratios and status labels
  - weekly_report.csv        bonus weekly summary
"""

import logging

import pandas as pd

from src.config import DAY_LABELS, OUT_DIR

logger = logging.getLogger(__name__)


def save_merged(merged: pd.DataFrame) -> None:
    """Write the full merged utilization table to CSV."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "merged_utilization.csv"
    merged.to_csv(path, index=False)
    logger.info("Saved → %s", path.name)


def save_weekly_report(results: dict, daily_avg: pd.DataFrame) -> None:
    """Write the bonus weekly summary CSV with per-day averages and status flags."""
    rows = []
    for _, row in daily_avg.iterrows():
        rows.append(
            {
                "day": row.get("day", row["date"]),
                "date": row["date"],
                "avg_utilization": row["utilization"],
                "status": (
                    "Overloaded"
                    if row["utilization"] > 1.0
                    else "Watch" if row["utilization"] >= 0.5 else "Free"
                ),
            }
        )

    # Append weekly summary row
    rows.append(
        {
            "day": "WEEK TOTAL",
            "date": "—",
            "avg_utilization": results["weekly_avg"],
            "status": f"{results['pct'].get('Overloaded', 0)}% overloaded",
        }
    )

    path = OUT_DIR / "weekly_report.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    logger.info("Saved → %s", path.name)
